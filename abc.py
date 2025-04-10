import json
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import logging
import os
from typing import List, Dict, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("lounge_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LoungeScraper:
    def __init__(self, base_url: str, output_dir: str = "output", max_pages: int = 10):
        """
        Initialize the lounge scraper.
        
        Args:
            base_url: The base URL pattern to scrape (with {page_num} as placeholder)
            output_dir: Directory to save output files
            max_pages: Maximum number of pages to scrape
        """
        self.base_url = base_url
        self.output_dir = output_dir
        self.max_pages = max_pages
        self.results = []
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def _extract_lounge_info(self, lounge_card) -> Dict[str, Any]:
        """Extract information from a lounge card element"""
        lounge_data = {}
        
        try:
            # Extract lounge name
            title_tag = lounge_card.select_one('h2 a')
            if title_tag:
                lounge_data['name'] = title_tag.text.strip()
                lounge_data['url'] = title_tag.get('href')
            
            # Extract location information
            location_div = lounge_card.select_one('.geodir-output-location')
            if location_div:
                # Extract operator info if available
                operator_div = location_div.select_one('.operatoralliance_listing_operator')
                if operator_div:
                    operator_tag = operator_div.select_one('a')
                    if operator_tag:
                        lounge_data['operator'] = operator_tag.text.strip()
                
                # Extract address
                address_div = location_div.select_one('.geodir_address')
                if address_div:
                    address_span = address_div.select_one('.address_details')
                    if address_span:
                        lounge_data['location'] = address_span.text.strip()
                
                # Extract business hours
                hours_div = location_div.select_one('.geodir-field-business_hours')
                if hours_div:
                    hours_data = {}
                    day_divs = hours_div.select('.gd-bh-days-list')
                    for day_div in day_divs:
                        day_name = day_div.select_one('.gd-bh-days-d')
                        hours_slot = day_div.select_one('.gd-bh-slot-r')
                        if day_name and hours_slot:
                            day = day_name.text.strip()
                            hours = hours_slot.text.strip()
                            hours_data[day] = hours
                    lounge_data['hours'] = hours_data
                
                # Extract amenities
                amenities_div = location_div.select_one('.geodir_more_info.amenities')
                if amenities_div:
                    amenities = []
                    amenity_imgs = amenities_div.select('img')
                    for img in amenity_imgs:
                        title = img.get('title')
                        if title:
                            name, status = title.split(': ')
                            amenities.append({'name': name, 'available': status == 'yes'})
                    lounge_data['amenities'] = amenities
            
            # Extract rating
            rating_div = lounge_card.select_one('.geodir-post-rating-value-1, .geodir-post-rating-value-2, .geodir-post-rating-value-3, .geodir-post-rating-value-4, .geodir-post-rating-value-5')
            if rating_div:
                rating_class = rating_div.get('class', [])
                rating_value = 0
                for cls in rating_class:
                    if cls.startswith('geodir-post-rating-value-'):
                        try:
                            rating_value = int(cls.split('-')[-1])
                        except (ValueError, IndexError):
                            pass
                lounge_data['rating'] = rating_value
            
            # Extract badges
            badges_div = lounge_card.select_one('.badges-container')
            if badges_div:
                badges = []
                badge_spans = badges_div.select('.gd-badge')
                for badge in badge_spans:
                    badge_text = badge.text.strip()
                    if badge_text:
                        badges.append(badge_text)
                if badges:
                    lounge_data['badges'] = badges
            
            # Check for online booking
            book_now_badge = lounge_card.select_one('.book-now-badge-details')
            if book_now_badge:
                lounge_data['online_booking_available'] = True
            
        except Exception as e:
            logger.error(f"Error extracting lounge data: {e}")
            
        return lounge_data
        
    def scrape_page(self, page_num: int) -> List[Dict[str, Any]]:
        """
        Scrape a single page of lounge data.
        
        Args:
            page_num: The page number to scrape
            
        Returns:
            List of dictionaries containing lounge information
        """
        url = self.base_url.format(page_num=page_num)
        logger.info(f"Scraping page {page_num}: {url}")
        
        lounges = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            try:
                # Navigate to the page
                page.goto(url, wait_until="networkidle")
                
                # Wait for content to load
                page.wait_for_selector('.geodir-loop-container', timeout=30000)
                
                # Get page content
                html_content = page.content()
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Check if we have results
                lounge_cards = soup.select('.geodir-post')
                
                if not lounge_cards:
                    logger.warning(f"No lounges found on page {page_num}")
                    return []
                
                # Extract information from each lounge card
                for card in lounge_cards:
                    lounge_data = self._extract_lounge_info(card)
                    if lounge_data:
                        lounges.append(lounge_data)
                
                logger.info(f"Found {len(lounges)} lounges on page {page_num}")
                
            except Exception as e:
                logger.error(f"Error scraping page {page_num}: {e}")
            
            finally:
                browser.close()
        
        return lounges
    
    def scrape_all_pages(self) -> None:
        """Scrape all pages up to max_pages"""
        all_lounges = []
        
        for page_num in range(1, self.max_pages + 1):
            # Scrape the current page
            page_lounges = self.scrape_page(page_num)
            
            # If no lounges found, we've likely reached the end
            if not page_lounges:
                logger.info(f"No more lounges found after page {page_num-1}")
                break
            
            all_lounges.extend(page_lounges)
            
            # Save progress after each page
            self.save_lounges(all_lounges, f"lounges_page_{page_num}.json")
            
            # Add a short delay between requests
            time.sleep(2)
        
        # Save the final complete dataset
        self.save_lounges(all_lounges, "lounges_all.json")
        logger.info(f"Scraped a total of {len(all_lounges)} lounges")
    
    def save_lounges(self, lounges: List[Dict[str, Any]], filename: str) -> None:
        """Save lounges to a JSON file"""
        output_path = os.path.join(self.output_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(lounges, f, indent=4, ensure_ascii=False)
        logger.info(f"Saved {len(lounges)} lounges to {output_path}")

def main():
    # Base URL pattern with page number placeholder
    base_url = "https://loungereview.com/page/{page_num}/?geodir_search=1&stype=gd_place&s&sgeo_lat&sgeo_lon&snear&sairline%5B0%5D&salliance%5B0%5D&soperator%5B0%5D&smemberships%5B0%5D="
    
    # Create and run the scraper
    scraper = LoungeScraper(base_url=base_url, max_pages=10)
    scraper.scrape_all_pages()

if __name__ == "__main__":
    main()
