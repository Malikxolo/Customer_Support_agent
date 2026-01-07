# global_config.py
from typing import Optional
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

class BrainHeartSettings:
    def __init__(self, brain_provider: Optional[str], brain_model: Optional[str],
                 customer_bot_analysis_provider: Optional[str], customer_bot_analysis_model: Optional[str],
                 customer_bot_response_provider: Optional[str], customer_bot_response_model: Optional[str],
                 use_premium_search: bool, web_model: Optional[str]):
        self.brain_provider = brain_provider
        self.brain_model = brain_model
        self.customer_bot_analysis_provider = customer_bot_analysis_provider
        self.customer_bot_analysis_model = customer_bot_analysis_model
        self.customer_bot_response_provider = customer_bot_response_provider
        self.customer_bot_response_model = customer_bot_response_model
        self.use_premium_search = use_premium_search
        self.web_model = web_model

settings = BrainHeartSettings(
    brain_provider=os.getenv('BRAIN_LLM_PROVIDER'),
    brain_model=os.getenv('BRAIN_LLM_MODEL'),
    customer_bot_analysis_provider=os.getenv('CUSTOMER_BOT_ANALYSIS_LLM_PROVIDER'),
    customer_bot_analysis_model=os.getenv('CUSTOMER_BOT_ANALYSIS_LLM_MODEL'),
    customer_bot_response_provider=os.getenv('CUSTOMER_BOT_RESPONSE_LLM_PROVIDER'),
    customer_bot_response_model=os.getenv('CUSTOMER_BOT_RESPONSE_LLM_MODEL'),
    use_premium_search=os.getenv('USE_PREMIUM_SEARCH', 'false').lower() == 'true',
    web_model=os.getenv('WEB_MODEL', None)
)
