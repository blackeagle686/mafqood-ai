from celery import shared_task
import logging
from app.core.scraper_agent import SocialMediaScraperAgent

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_scraped_post_task(self, post_data: dict):
    """
    Background Celery task that takes a payload from a social media scraping listener
    (or external system pushing updates) and processes it via the Scraper Agent.
    """
    logger.info(f"Starting background processing for scraped post: {post_data.get('post_id')}")
    try:
        agent = SocialMediaScraperAgent()
        result = agent.process_social_post(post_data)
        
        if result.get("status") == "success":
            logger.info(f"Scraper Agent processed post successfully: {result}")
        else:
            logger.warning(f"Scraper Agent rejected/failed post: {result}")
            
        return result
        
    except Exception as e:
        logger.error(f"Error in process_scraped_post_task: {e}")
        self.retry(exc=e, countdown=60)
