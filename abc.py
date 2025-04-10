"""
This script parses lounge information directly from the provided HTML sample.
Use this if the web scraping approach fails due to website restrictions.
"""

import json
import os
from bs4 import BeautifulSoup
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_lounge_info(lounge_card):
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
                        amenity_parts = title.split(': ')
                        if len(amenity_parts) == 2:
                            name, status = amenity_parts
                            amenities.append({'name': name, 'available': status.lower() == 'yes'})
                lounge_data['amenities'] = amenities
        
        # Extract rating
        rating_div = lounge_card.select_one('[class*="geodir-post-rating-value-"]')
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

def parse_html_file(file_path):
    """Parse the HTML file and extract lounge information"""
    logger.info(f"Parsing HTML file: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all lounge cards
        lounge_cards = soup.select('.geodir-post')
        
        if not lounge_cards:
            logger.warning("No lounge cards found using '.geodir-post' selector")
            # Try alternative selectors
            lounge_cards = soup.select('.col.mb-4')
        
        logger.info(f"Found {len(lounge_cards)} lounge cards")
        
        # Extract information from each lounge card
        lounges = []
        for card in lounge_cards:
            lounge_data = extract_lounge_info(card)
            if lounge_data and lounge_data.get('name'):  # Only add if we have a name at minimum
                lounges.append(lounge_data)
        
        logger.info(f"Successfully extracted data for {len(lounges)} lounges")
        
        return lounges
    
    except Exception as e:
        logger.error(f"Error parsing HTML file: {e}")
        return []

def save_to_json(lounges, output_path):
    """Save the extracted lounges to a JSON file"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(lounges, f, indent=4, ensure_ascii=False)
        
        logger.info(f"Saved {len(lounges)} lounges to {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving to JSON: {e}")
        return False

def main():
    # Path to the sample HTML file
    sample_html_file = "Newcastle (NCL) Airport lounges _ LoungeReview.com.html"
    
    # Check if file exists
    if not os.path.exists(sample_html_file):
        logger.error(f"File not found: {sample_html_file}")
        return
    
    # Parse the HTML file
    lounges = parse_html_file(sample_html_file)
    
    if lounges:
        # Save the results
        output_path = "output/lounges_from_sample.json"
        save_to_json(lounges, output_path)
    else:
        logger.error("No lounges extracted from the sample HTML")

if __name__ == "__main__":
    main()