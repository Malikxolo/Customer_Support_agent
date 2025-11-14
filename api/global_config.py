# global_config.py
from typing import Optional
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

class BrainHeartSettings:
    def __init__(self, brain_provider: Optional[str], brain_model: Optional[str],
                 heart_provider: Optional[str], heart_model: Optional[str],
                 router_provider: Optional[str], router_model: Optional[str],
                 use_premium_search: bool, web_model: Optional[str]):
        self.brain_provider = brain_provider
        self.brain_model = brain_model
        self.heart_provider = heart_provider
        self.heart_model = heart_model
        self.router_provider = router_provider
        self.router_model = router_model
        self.use_premium_search = use_premium_search
        self.web_model = web_model

settings = BrainHeartSettings(
    brain_provider=os.getenv('BRAIN_LLM_PROVIDER'),
    brain_model=os.getenv('BRAIN_LLM_MODEL'),
    heart_provider=os.getenv('HEART_LLM_PROVIDER'),
    heart_model=os.getenv('HEART_LLM_MODEL'),
    router_provider=os.getenv('ROUTER_LLM_PROVIDER'),
    router_model=os.getenv('ROUTER_LLM_MODEL'),
    use_premium_search=os.getenv('USE_PREMIUM_SEARCH', 'false').lower() == 'true',
    web_model=os.getenv('WEB_MODEL', None)
)
