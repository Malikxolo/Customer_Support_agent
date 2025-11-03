"""
Redis Cache Manager for Brain-Heart Deep Research System
Handles query caching, tool results caching, and scraping confirmation flow
"""

import os
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import redis.asyncio as redis

from .config import SCRAPING_CONFIRMATION_TTL

logger = logging.getLogger(__name__)


class RedisCacheManager:
    """Redis-based cache manager for queries and tool results"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = False
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection from environment variables"""
        try:
            redis_host = os.getenv('REDIS_HOST')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_password = os.getenv('REDIS_PASSWORD')
            redis_username = os.getenv('REDIS_USERNAME', 'default')
            
            if redis_host:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    username=redis_username,
                    password=redis_password,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                self.enabled = True
                logger.info(f"✅ Redis cache manager initialized: {redis_host}:{redis_port}")
            else:
                logger.warning("⚠️ Redis not configured - caching disabled")
        except Exception as e:
            logger.error(f"❌ Redis initialization failed: {e}")
            self.enabled = False
    
    def _generate_cache_key(self, prefix: str, data: str, user_id: str = None) -> str:
        """Generate a unique cache key using hash"""
        key_data = f"{data}_{user_id or 'anonymous'}"
        hash_key = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{hash_key}"
    
    async def get_cached_query(self, query: str, user_id: str = None) -> Optional[Dict]:
        """Get cached analysis for a query"""
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            cache_key = self._generate_cache_key("query_analysis", query, user_id)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                logger.info(f"🎯 Cache HIT for query: {query[:50]}...")
                return json.loads(cached_data)
            else:
                logger.info(f"❌ Cache MISS for query: {query[:50]}...")
                return None
        except Exception as e:
            logger.error(f"❌ Redis get error: {e}")
            return None
    
    async def cache_query(self, query: str, analysis: Dict, user_id: str = None, ttl: int = 3600):
        """Cache query analysis with TTL (default 1 hour)"""
        if not self.enabled or not self.redis_client:
            return
        
        try:
            cache_key = self._generate_cache_key("query_analysis", query, user_id)
            await self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(analysis, ensure_ascii=False)
            )
            logger.info(f"💾 Cached query analysis: {query[:50]}... (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"❌ Redis set error: {e}")
    
    async def get_cached_tool_data(self, tool_results: Dict, user_id: str = None) -> Optional[str]:
        """Get cached formatted tool data"""
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            # Create a hash from tool results structure
            tool_key = json.dumps(tool_results, sort_keys=True)
            cache_key = self._generate_cache_key("tool_data", tool_key, user_id)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                logger.info(f"🎯 Cache HIT for formatted tool data")
                return cached_data
            else:
                logger.info(f"❌ Cache MISS for formatted tool data")
                return None
        except Exception as e:
            logger.error(f"❌ Redis get error for tool data: {e}")
            return None
    
    async def cache_tool_data(self, tool_results: Dict, formatted_data: str, user_id: str = None, ttl: int = 7200):
        """Cache formatted tool data with TTL (default 2 hours)"""
        if not self.enabled or not self.redis_client:
            return
        
        try:
            tool_key = json.dumps(tool_results, sort_keys=True)
            cache_key = self._generate_cache_key("tool_data", tool_key, user_id)
            await self.redis_client.setex(
                cache_key,
                ttl,
                formatted_data
            )
            logger.info(f"💾 Cached formatted tool data (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"❌ Redis set error for tool data: {e}")
    
    async def get_cached_tool_results(self, query: str, tools: List[str], user_id: str = None, scraping_guidance: Dict = None) -> Optional[Dict]:
        """Get cached tool execution results for a query (includes scraping guidance in key)"""
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            # Create cache key from query + tools combination + scraping guidance
            tools_str = json.dumps(sorted(tools))
            scraping_str = json.dumps(scraping_guidance, sort_keys=True) if scraping_guidance else ""
            cache_data = f"{query}_{tools_str}_{scraping_str}"
            cache_key = self._generate_cache_key("tool_results", cache_data, user_id)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                logger.info(f"🎯 Cache HIT for tool results: {query[:50]}...")
                return json.loads(cached_data)
            else:
                logger.info(f"❌ Cache MISS for tool results: {query[:50]}...")
                return None
        except Exception as e:
            logger.error(f"❌ Redis get error for tool results: {e}")
            return None
    
    async def cache_tool_results(self, query: str, tools: List[str], tool_results: Dict, user_id: str = None, scraping_guidance: Dict = None, ttl: int = 3600):
        """Cache tool execution results with TTL (default 1 hour) - includes scraping guidance in key"""
        if not self.enabled or not self.redis_client:
            return
        
        try:
            # Create cache key from query + tools combination + scraping guidance
            tools_str = json.dumps(sorted(tools))
            scraping_str = json.dumps(scraping_guidance, sort_keys=True) if scraping_guidance else ""
            cache_data = f"{query}_{tools_str}_{scraping_str}"
            cache_key = self._generate_cache_key("tool_results", cache_data, user_id)
            await self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(tool_results, ensure_ascii=False)
            )
            logger.info(f"💾 Cached tool results for: {query[:50]}... (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"❌ Redis set error for tool results: {e}")
    
    async def clear_user_cache(self, user_id: str):
        """Clear all cache for a specific user"""
        if not self.enabled or not self.redis_client:
            return
        
        try:
            # Scan for user-specific keys
            pattern = f"*{user_id}*"
            cursor = 0
            deleted_count = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
                if keys:
                    await self.redis_client.delete(*keys)
                    deleted_count += len(keys)
                if cursor == 0:
                    break
            
            logger.info(f"🗑️ Cleared {deleted_count} cache entries for user: {user_id}")
        except Exception as e:
            logger.error(f"❌ Redis clear error: {e}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.enabled or not self.redis_client:
            return {"enabled": False}
        
        try:
            info = await self.redis_client.info()
            return {
                "enabled": True,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "total_keys": await self.redis_client.dbsize()
            }
        except Exception as e:
            logger.error(f"❌ Redis stats error: {e}")
            return {"enabled": False, "error": str(e)}
    
    # ==================== CONFIRMATION FLOW METHODS ====================
    
    async def set_pending_confirmation(self, token: str, payload: Dict, user_id: str, ttl: int = None) -> bool:
        """
        Store a pending confirmation action in Redis
        
        Args:
            token: Unique confirmation token (UUID)
            payload: Dict containing query, analysis, tools, scraping_guidance, etc.
            user_id: User ID for security validation
            ttl: Time-to-live in seconds (default: SCRAPING_CONFIRMATION_TTL)
        
        Returns:
            True if stored successfully, False otherwise
        """
        if not self.enabled or not self.redis_client:
            logger.warning("⚠️ Redis not enabled, cannot store pending confirmation")
            return False
        
        try:
            ttl = ttl or SCRAPING_CONFIRMATION_TTL
            cache_key = f"pending_confirm:{token}"
            
            # Add metadata
            payload["user_id"] = user_id
            payload["token"] = token
            payload["created_at"] = datetime.now().isoformat()
            
            await self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(payload, ensure_ascii=False)
            )
            
            logger.info(f"💾 Stored pending confirmation: {token} for user {user_id} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to store pending confirmation: {e}")
            return False
    
    async def get_pending_confirmation(self, token: str) -> Optional[Dict]:
        """
        Retrieve a pending confirmation by token
        
        Args:
            token: Confirmation token
        
        Returns:
            Payload dict if found, None otherwise
        """
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            cache_key = f"pending_confirm:{token}"
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                logger.info(f"🎯 Retrieved pending confirmation: {token}")
                return json.loads(cached_data)
            else:
                logger.debug(f"❌ No pending confirmation found for token: {token}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error retrieving pending confirmation: {e}")
            return None
    
    async def get_pending_confirmation_for_user(self, user_id: str) -> Optional[Dict]:
        """
        Retrieve the most recent pending confirmation for a user
        
        Args:
            user_id: User ID
        
        Returns:
            Payload dict if found, None otherwise
        """
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            # Scan for user's pending confirmations
            pattern = f"pending_confirm:*"
            cursor = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
                
                for key in keys:
                    cached_data = await self.redis_client.get(key)
                    if cached_data:
                        payload = json.loads(cached_data)
                        if payload.get("user_id") == user_id:
                            logger.info(f"🎯 Found pending confirmation for user: {user_id}")
                            return payload
                
                if cursor == 0:
                    break
            
            logger.debug(f"❌ No pending confirmation found for user: {user_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error searching pending confirmations: {e}")
            return None
    
    async def delete_pending_confirmation(self, token: str) -> bool:
        """
        Delete a pending confirmation
        
        Args:
            token: Confirmation token
        
        Returns:
            True if deleted, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            cache_key = f"pending_confirm:{token}"
            deleted = await self.redis_client.delete(cache_key)
            
            if deleted:
                logger.info(f"🗑️ Deleted pending confirmation: {token}")
                return True
            else:
                logger.debug(f"⚠️ No pending confirmation to delete: {token}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error deleting pending confirmation: {e}")
            return False
    
    async def cancel_all_pending_confirmations_for_user(self, user_id: str) -> int:
        """
        Cancel (delete) all pending confirmations for a specific user
        Used when user sends a new non-confirmation query to prevent accidental resumption
        
        Args:
            user_id: User ID
        
        Returns:
            Number of pending confirmations cancelled
        """
        if not self.enabled or not self.redis_client:
            return 0
        
        try:
            # Scan for user's pending confirmations
            pattern = f"pending_confirm:*"
            cursor = 0
            cancelled_count = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
                
                for key in keys:
                    cached_data = await self.redis_client.get(key)
                    if cached_data:
                        payload = json.loads(cached_data)
                        if payload.get("user_id") == user_id:
                            # Delete this pending confirmation
                            token = payload.get("token")
                            await self.redis_client.delete(key)
                            logger.info(f"🔻 Superseded pending confirmation {token} for user {user_id}")
                            cancelled_count += 1
                
                if cursor == 0:
                    break
            
            if cancelled_count > 0:
                logger.info(f"✅ Cancelled {cancelled_count} pending confirmation(s) for user {user_id}")
            
            return cancelled_count
            
        except Exception as e:
            logger.error(f"❌ Error cancelling pending confirmations: {e}")
            return 0
