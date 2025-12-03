"""
Zapier MCP Integration
======================

High-level Zapier-specific wrapper around MCP client.
Provides easy integration with OptimizedAgent and tool_manager.

Features:
    - Pre-configured for Zapier MCP server
    - Tool categorization (email, CRM, sheets, etc.)
    - Integration with existing tool_manager
    - Quota/rate limit management
    - Usage analytics

Usage:
    from core.mcp import ZapierMCPClient, MCPSecurityManager
    
    security = MCPSecurityManager()
    zapier = ZapierMCPClient(security)
    
    await zapier.connect()
    
    # List all available Zapier actions
    tools = await zapier.list_available_tools()
    
    # Execute a Gmail action
    result = await zapier.execute_action("gmail_send_email", {
        "to": "user@example.com",
        "subject": "Hello from AI",
        "body": "This is an automated message."
    })

Integration with OptimizedAgent:
    The ZapierToolManager class provides a bridge between
    Zapier MCP and the existing tool_manager pattern.

"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .security import MCPSecurityManager, MCPCredentials
from .client import MCPClient, MCPTool, MCPToolResult
from .transport import StreamableHTTPTransport, RateLimiter
from .exceptions import (
    MCPError,
    MCPAuthenticationError,
    MCPConnectionError,
    MCPToolExecutionError,
    MCPRateLimitError
)

logger = logging.getLogger(__name__)


class ZapierToolCategory(Enum):
    """Categories for Zapier tools"""
    EMAIL = "email"
    CRM = "crm"
    SPREADSHEET = "spreadsheet"
    CALENDAR = "calendar"
    MESSAGING = "messaging"
    PROJECT = "project"
    STORAGE = "storage"
    SOCIAL = "social"
    ECOMMERCE = "ecommerce"
    SUPPORT = "support"
    AUTOMATION = "automation"
    DATABASE = "database"
    MARKETING = "marketing"
    ANALYTICS = "analytics"
    FINANCE = "finance"
    HR = "hr"
    OTHER = "other"


@dataclass
class ZapierTool:
    """
    Extended tool information for Zapier actions.
    
    Adds Zapier-specific metadata to base MCPTool.
    """
    mcp_tool: MCPTool
    app_name: str  # e.g., "Gmail", "Slack", "Notion"
    action_name: str  # e.g., "Send Email", "Post Message"
    category: ZapierToolCategory = ZapierToolCategory.OTHER
    requires_auth: bool = True
    is_configured: bool = True  # Zapier tools are pre-configured
    
    @property
    def name(self) -> str:
        return self.mcp_tool.name
    
    @property
    def description(self) -> str:
        return self.mcp_tool.description
    
    @property
    def display_name(self) -> str:
        return f"{self.app_name}: {self.action_name}"
    
    @property
    def required_params(self) -> List[str]:
        return self.mcp_tool.required_params
    
    @property
    def optional_params(self) -> List[str]:
        return self.mcp_tool.optional_params
    
    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        return self.mcp_tool.validate_params(params)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "app_name": self.app_name,
            "action_name": self.action_name,
            "category": self.category.value,
            "description": self.description,
            "requires_auth": self.requires_auth,
            "is_configured": self.is_configured,
            "required_params": self.required_params,
            "optional_params": self.optional_params,
            "input_schema": self.mcp_tool.input_schema
        }


class ZapierMCPClient:
    """
    Zapier-specific MCP client.
    
    High-level wrapper that provides:
        - Easy Zapier MCP connection
        - Tool discovery and categorization
        - Action execution with Zapier semantics
        - Integration helpers for OptimizedAgent
        - Usage tracking and analytics
    """
    
    # Tool name prefixes to category mapping
    CATEGORY_PREFIXES = {
        # Email
        "gmail": ZapierToolCategory.EMAIL,
        "outlook": ZapierToolCategory.EMAIL,
        "sendgrid": ZapierToolCategory.EMAIL,
        "mailchimp": ZapierToolCategory.EMAIL,
        "mailgun": ZapierToolCategory.EMAIL,
        "postmark": ZapierToolCategory.EMAIL,
        
        # Messaging
        "slack": ZapierToolCategory.MESSAGING,
        "discord": ZapierToolCategory.MESSAGING,
        "teams": ZapierToolCategory.MESSAGING,
        "telegram": ZapierToolCategory.MESSAGING,
        "whatsapp": ZapierToolCategory.MESSAGING,
        "twilio": ZapierToolCategory.MESSAGING,
        "sms": ZapierToolCategory.MESSAGING,
        
        # Spreadsheet
        "google_sheets": ZapierToolCategory.SPREADSHEET,
        "sheets": ZapierToolCategory.SPREADSHEET,
        "excel": ZapierToolCategory.SPREADSHEET,
        "airtable": ZapierToolCategory.SPREADSHEET,
        "smartsheet": ZapierToolCategory.SPREADSHEET,
        
        # Project Management
        "notion": ZapierToolCategory.PROJECT,
        "trello": ZapierToolCategory.PROJECT,
        "asana": ZapierToolCategory.PROJECT,
        "jira": ZapierToolCategory.PROJECT,
        "monday": ZapierToolCategory.PROJECT,
        "clickup": ZapierToolCategory.PROJECT,
        "basecamp": ZapierToolCategory.PROJECT,
        "todoist": ZapierToolCategory.PROJECT,
        
        # Calendar
        "calendar": ZapierToolCategory.CALENDAR,
        "google_calendar": ZapierToolCategory.CALENDAR,
        "outlook_calendar": ZapierToolCategory.CALENDAR,
        "calendly": ZapierToolCategory.CALENDAR,
        
        # CRM
        "salesforce": ZapierToolCategory.CRM,
        "hubspot": ZapierToolCategory.CRM,
        "pipedrive": ZapierToolCategory.CRM,
        "zoho": ZapierToolCategory.CRM,
        "copper": ZapierToolCategory.CRM,
        "freshsales": ZapierToolCategory.CRM,
        
        # Support
        "zendesk": ZapierToolCategory.SUPPORT,
        "intercom": ZapierToolCategory.SUPPORT,
        "freshdesk": ZapierToolCategory.SUPPORT,
        "helpscout": ZapierToolCategory.SUPPORT,
        "crisp": ZapierToolCategory.SUPPORT,
        
        # E-commerce
        "shopify": ZapierToolCategory.ECOMMERCE,
        "stripe": ZapierToolCategory.ECOMMERCE,
        "woocommerce": ZapierToolCategory.ECOMMERCE,
        "square": ZapierToolCategory.ECOMMERCE,
        "paypal": ZapierToolCategory.ECOMMERCE,
        
        # Storage
        "google_drive": ZapierToolCategory.STORAGE,
        "drive": ZapierToolCategory.STORAGE,
        "dropbox": ZapierToolCategory.STORAGE,
        "onedrive": ZapierToolCategory.STORAGE,
        "box": ZapierToolCategory.STORAGE,
        
        # Social
        "twitter": ZapierToolCategory.SOCIAL,
        "facebook": ZapierToolCategory.SOCIAL,
        "instagram": ZapierToolCategory.SOCIAL,
        "linkedin": ZapierToolCategory.SOCIAL,
        "youtube": ZapierToolCategory.SOCIAL,
        "tiktok": ZapierToolCategory.SOCIAL,
        
        # Database
        "mysql": ZapierToolCategory.DATABASE,
        "postgres": ZapierToolCategory.DATABASE,
        "mongodb": ZapierToolCategory.DATABASE,
        "firebase": ZapierToolCategory.DATABASE,
        "supabase": ZapierToolCategory.DATABASE,
        
        # Marketing
        "mailerlite": ZapierToolCategory.MARKETING,
        "convertkit": ZapierToolCategory.MARKETING,
        "activecampaign": ZapierToolCategory.MARKETING,
        "drip": ZapierToolCategory.MARKETING,
        
        # Analytics
        "google_analytics": ZapierToolCategory.ANALYTICS,
        "mixpanel": ZapierToolCategory.ANALYTICS,
        "amplitude": ZapierToolCategory.ANALYTICS,
        
        # Automation
        "zapier": ZapierToolCategory.AUTOMATION,
        "webhook": ZapierToolCategory.AUTOMATION,
        "code": ZapierToolCategory.AUTOMATION,
    }
    
    def __init__(
        self,
        security_manager: MCPSecurityManager,
        timeout: int = 60,  # Increased from 30 - Zapier operations can be slow
        max_retries: int = 2,  # Reduced from 3 - retrying write ops is dangerous
        cache_tools: bool = True,
        tool_cache_ttl: int = 300
    ):
        """
        Initialize Zapier MCP client.
        
        Args:
            security_manager: Security manager for credentials
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            cache_tools: Whether to cache tool definitions
            tool_cache_ttl: Tool cache TTL in seconds
        """
        self.security_manager = security_manager
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_tools = cache_tools
        self.tool_cache_ttl = tool_cache_ttl
        
        self._client: Optional[MCPClient] = None
        self._tools: Dict[str, ZapierTool] = {}
        self._connected = False
        self._connection_time: Optional[datetime] = None
        
        # Usage tracking
        self._action_count = 0
        self._success_count = 0
        self._error_count = 0
        self._actions_by_category: Dict[str, int] = {}
        self._actions_by_tool: Dict[str, int] = {}
        
        logger.info("✅ ZapierMCPClient initialized")
    
    async def connect(self) -> bool:
        """
        Connect to Zapier MCP server.
        
        Returns:
            True if connection successful
            
        Raises:
            MCPConnectionError: If connection fails
            MCPAuthenticationError: If credentials invalid
        """
        # Check if Zapier is configured
        if not self.security_manager.is_zapier_configured():
            logger.error("❌ Zapier MCP not configured. Set ZAPIER_MCP_SERVER_URL in .env")
            raise MCPConnectionError(
                "Zapier MCP not configured. Please set ZAPIER_MCP_SERVER_URL in .env"
            )
        
        try:
            # Get credentials
            creds = self.security_manager.get_zapier_credentials()
            if not creds:
                raise MCPAuthenticationError("Failed to get Zapier credentials")
            
            logger.info(f"🔗 Connecting to Zapier MCP: {creds.masked_url}")
            
            # Create rate limiter (Zapier has limits based on plan)
            rate_limiter = RateLimiter(
                requests_per_minute=60,  # Default, adjust based on Zapier plan
                requests_per_second=2.0
            )
            
            # Create transport
            transport = StreamableHTTPTransport(
                server_url=creds.server_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
                rate_limiter=rate_limiter
            )
            
            # Create client
            self._client = MCPClient(
                transport=transport,
                cache_tools=self.cache_tools,
                tool_cache_ttl=self.tool_cache_ttl
            )
            
            # Connect
            self._connected = await self._client.connect()
            
            if self._connected:
                self._connection_time = datetime.now(timezone.utc)
                logger.info("✅ Connected to Zapier MCP")
                
                # Load and categorize tools
                await self.refresh_tools()
            
            return self._connected
            
        except MCPError:
            raise
        except Exception as e:
            logger.error(f"❌ Zapier connection failed: {e}")
            raise MCPConnectionError(f"Failed to connect to Zapier: {e}")
    
    async def disconnect(self) -> None:
        """
        Disconnect from Zapier MCP server.
        """
        if self._client:
            await self._client.disconnect()
        
        self._connected = False
        self._tools.clear()
        
        # Log usage stats on disconnect
        logger.info(f"✅ Disconnected from Zapier MCP")
        logger.info(f"   Total actions: {self._action_count}")
        logger.info(f"   Success rate: {self._success_count / max(self._action_count, 1) * 100:.1f}%")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Zapier"""
        return self._connected and self._client is not None and self._client.is_connected
    
    async def refresh_tools(self) -> List[ZapierTool]:
        """
        Refresh available Zapier tools.
        
        Returns:
            List of available Zapier tools
        """
        if not self._client:
            raise MCPConnectionError("Not connected to Zapier")
        
        # Fetch raw tools
        mcp_tools = await self._client.list_tools(force_refresh=True)
        
        # Convert to ZapierTools with categorization
        self._tools.clear()
        for mcp_tool in mcp_tools:
            zapier_tool = self._categorize_tool(mcp_tool)
            self._tools[zapier_tool.name] = zapier_tool
        
        logger.info(f"✅ Loaded {len(self._tools)} Zapier tools")
        
        # Log category breakdown
        category_counts = {}
        for tool in self._tools.values():
            cat = tool.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1])[:5]:
            logger.info(f"   {cat}: {count} tools")
        
        return list(self._tools.values())
    
    def _categorize_tool(self, mcp_tool: MCPTool) -> ZapierTool:
        """Categorize an MCP tool based on its name"""
        name_lower = mcp_tool.name.lower()
        
        # Find category by checking prefixes
        category = ZapierToolCategory.OTHER
        for prefix, cat in self.CATEGORY_PREFIXES.items():
            if name_lower.startswith(prefix) or f"_{prefix}" in name_lower:
                category = cat
                break
        
        # Extract app and action names from tool name
        # Common patterns: "gmail_send_email", "slack_post_message"
        parts = mcp_tool.name.split("_")
        
        if len(parts) >= 2:
            # First part(s) are usually the app name
            app_name = parts[0].replace("_", " ").title()
            
            # Rest is the action
            action_parts = parts[1:]
            action_name = " ".join(action_parts).replace("_", " ").title()
        else:
            app_name = mcp_tool.name.title()
            action_name = "Action"
        
        # Use description for better action name if available
        if mcp_tool.description:
            # First sentence of description is usually the action
            first_sentence = mcp_tool.description.split(".")[0]
            if len(first_sentence) < 50:
                action_name = first_sentence
        
        return ZapierTool(
            mcp_tool=mcp_tool,
            app_name=app_name,
            action_name=action_name,
            category=category,
            requires_auth=True,
            is_configured=True
        )
    
    async def list_available_tools(
        self,
        category: Optional[ZapierToolCategory] = None,
        search: Optional[str] = None
    ) -> List[ZapierTool]:
        """
        Get list of available Zapier tools with optional filtering.
        
        Args:
            category: Filter by category
            search: Search in tool names and descriptions
            
        Returns:
            List of matching tools
        """
        if not self._tools:
            await self.refresh_tools()
        
        tools = list(self._tools.values())
        
        # Filter by category
        if category:
            tools = [t for t in tools if t.category == category]
        
        # Filter by search term
        if search:
            search_lower = search.lower()
            tools = [
                t for t in tools
                if search_lower in t.name.lower() 
                or search_lower in t.description.lower()
                or search_lower in t.app_name.lower()
            ]
        
        return tools
    
    async def get_tool(self, tool_name: str) -> Optional[ZapierTool]:
        """Get specific tool by name"""
        if not self._tools:
            await self.refresh_tools()
        return self._tools.get(tool_name)
    
    async def get_tools_by_category(self, category: ZapierToolCategory) -> List[ZapierTool]:
        """Get all tools in a category"""
        return await self.list_available_tools(category=category)
    
    async def execute_action(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> MCPToolResult:
        """
        Execute a Zapier action.
        
        Args:
            tool_name: Name of Zapier tool/action
            params: Action parameters
            
        Returns:
            Execution result
            
        Raises:
            MCPConnectionError: If not connected
            MCPToolExecutionError: If tool execution fails
        """
        if not self._client:
            raise MCPConnectionError("Not connected to Zapier")
        
        # Track usage
        self._action_count += 1
        
        # Get tool for category tracking
        tool = await self.get_tool(tool_name)
        if tool:
            cat = tool.category.value
            self._actions_by_category[cat] = self._actions_by_category.get(cat, 0) + 1
        
        self._actions_by_tool[tool_name] = self._actions_by_tool.get(tool_name, 0) + 1
        
        logger.info(f"🚀 Executing Zapier action: {tool_name}")
        
        # Log params safely (mask sensitive data)
        safe_params = self.security_manager.mask_sensitive_data(params)
        logger.debug(f"   Params: {safe_params}")
        
        try:
            result = await self._client.call_tool(tool_name, params)
            
            if result.success:
                self._success_count += 1
                logger.info(f"✅ Action {tool_name} completed ({result.execution_time_ms:.1f}ms)")
            else:
                self._error_count += 1
                logger.error(f"❌ Action {tool_name} failed: {result.error}")
            
            return result
            
        except MCPError:
            self._error_count += 1
            raise
        except Exception as e:
            self._error_count += 1
            logger.error(f"❌ Unexpected error executing {tool_name}: {e}")
            raise MCPToolExecutionError(
                message=f"Unexpected error: {e}",
                tool_name=tool_name
            )
    
    async def execute_action_safe(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> MCPToolResult:
        """
        Execute action with error handling (never raises).
        
        Args:
            tool_name: Name of Zapier tool/action
            params: Action parameters
            
        Returns:
            Execution result (check success field)
        """
        try:
            return await self.execute_action(tool_name, params)
        except Exception as e:
            return MCPToolResult(
                success=False,
                tool_name=tool_name,
                error=str(e)
            )
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get detailed usage statistics"""
        return {
            "connected": self.is_connected,
            "connection_time": self._connection_time.isoformat() if self._connection_time else None,
            "tools_available": len(self._tools),
            "totals": {
                "actions_executed": self._action_count,
                "successful": self._success_count,
                "errors": self._error_count,
                "success_rate": self._success_count / max(self._action_count, 1) * 100
            },
            "by_category": dict(sorted(
                self._actions_by_category.items(), 
                key=lambda x: -x[1]
            )[:10]),
            "top_tools": dict(sorted(
                self._actions_by_tool.items(),
                key=lambda x: -x[1]
            )[:10])
        }
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get list of available categories with tool counts"""
        category_counts = {}
        for tool in self._tools.values():
            cat = tool.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        return [
            {"category": cat, "count": count}
            for cat, count in sorted(category_counts.items(), key=lambda x: -x[1])
        ]


class ZapierToolManager:
    """
    Bridge between ZapierMCPClient and OptimizedAgent's tool_manager.
    
    Provides the same interface as existing tools (web_search, rag, etc.)
    but routes to Zapier MCP for execution.
    
    Usage:
        # In tool_manager initialization
        zapier_manager = ZapierToolManager(security_manager)
        await zapier_manager.initialize()
        
        # Check available tools
        tool_names = zapier_manager.get_tool_names()
        
        # Execute (matches tool_manager interface)
        result = await zapier_manager.execute(
            query="Send email to john@example.com",
            tool_name="zapier_gmail_send_email",
            params={"to": "john@example.com", "subject": "Hi", "body": "Hello"}
        )
    """
    
    def __init__(
        self,
        security_manager: MCPSecurityManager,
        prefix: str = "zapier_",
        enabled_categories: Optional[List[ZapierToolCategory]] = None
    ):
        """
        Initialize Zapier tool manager.
        
        Args:
            security_manager: Security manager for credentials
            prefix: Prefix for tool names (e.g., "zapier_gmail_send_email")
            enabled_categories: Limit to specific categories (None = all)
        """
        self.security_manager = security_manager
        self.prefix = prefix
        self.enabled_categories = enabled_categories
        
        self._client: Optional[ZapierMCPClient] = None
        self._initialized = False
        self._tool_schemas: Dict[str, Dict[str, Any]] = {}
        
        logger.info("✅ ZapierToolManager initialized")
        if enabled_categories:
            logger.info(f"   Enabled categories: {[c.value for c in enabled_categories]}")
    
    async def initialize(self) -> bool:
        """
        Initialize Zapier connection and load tools.
        
        Returns:
            True if initialization successful
        """
        if not self.security_manager.is_zapier_configured():
            logger.warning("⚠️ Zapier MCP not configured - skipping initialization")
            return False
        
        try:
            self._client = ZapierMCPClient(self.security_manager)
            connected = await self._client.connect()
            
            if connected:
                # Load tool schemas for LLM
                tools = await self._client.list_available_tools()
                
                # Meta-tools to exclude - these are for Zapier configuration, not user actions
                META_TOOLS_TO_EXCLUDE = ['add_tools', 'edit_tools']
                
                for tool in tools:
                    # Skip meta-tools that shouldn't be exposed to users
                    if tool.name in META_TOOLS_TO_EXCLUDE:
                        logger.debug(f"   Skipping meta-tool: {tool.name}")
                        continue
                    
                    # Filter by category if specified
                    if self.enabled_categories and tool.category not in self.enabled_categories:
                        continue
                    
                    prefixed_name = f"{self.prefix}{tool.name}"
                    self._tool_schemas[prefixed_name] = self._generate_schema(tool)
                
                self._initialized = True
                logger.info(f"✅ ZapierToolManager initialized with {len(self._tool_schemas)} tools")
            
            return self._initialized
            
        except Exception as e:
            logger.error(f"❌ ZapierToolManager initialization failed: {e}")
            return False
    
    @property
    def is_initialized(self) -> bool:
        """Check if manager is initialized"""
        return self._initialized
    
    @property
    def is_available(self) -> bool:
        """Check if Zapier tools are available"""
        return self._initialized and self._client is not None and self._client.is_connected
    
    def get_tool_names(self) -> List[str]:
        """Get list of available Zapier tool names (with prefix)"""
        return list(self._tool_schemas.keys())
    
    def get_tool_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get tool schemas for LLM prompt generation"""
        return self._tool_schemas.copy()
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for specific tool"""
        return self._tool_schemas.get(tool_name)
    
    def get_tools_prompt(self) -> str:
        """
        Generate a dynamic prompt section for ALL available Zapier tools.
        
        This method creates a formatted string that can be directly included
        in LLM prompts, showing all tools with their descriptions and required parameters.
        
        The prompt automatically updates when tools are added/removed in Zapier,
        making it truly universal - NO code changes needed when adding new integrations.
        
        Returns:
            Formatted string with all Zapier tools for LLM prompts.
            Returns empty string if no tools available.
        """
        if not self._tool_schemas:
            return ""
        
        # Group tools by category for better organization
        tools_by_category: Dict[str, List[Dict[str, Any]]] = {}
        
        for tool_name, schema in self._tool_schemas.items():
            category = schema.get("category", "other")
            if category not in tools_by_category:
                tools_by_category[category] = []
            tools_by_category[category].append({
                "name": tool_name,
                "schema": schema
            })
        
        # Build the prompt
        lines = [
            f"- zapier_*: External app actions via Zapier MCP ({len(self._tool_schemas)} tools available)",
            "  NOTE: Zapier tools accept NATURAL LANGUAGE instructions (not structured JSON params)",
            "  IMPORTANT: Only use these tools for their intended purpose. If no matching tool exists, respond without using tools."
        ]
        
        for category, tools in sorted(tools_by_category.items()):
            lines.append(f"  [{category.upper()}]:")
            
            for tool_info in tools:
                schema = tool_info["schema"]
                tool_name = tool_info["name"]
                description = schema.get("description", "No description")
                lines.append(f"    * {tool_name}: {description}")
        
        return "\n".join(lines)
    
    def _generate_schema(self, tool: ZapierTool) -> Dict[str, Any]:
        """Generate tool schema for LLM"""
        return {
            "name": f"{self.prefix}{tool.name}",
            "display_name": tool.display_name,
            "description": tool.description,
            "category": tool.category.value,
            "app": tool.app_name,
            "action": tool.action_name,
            "parameters": tool.mcp_tool.input_schema,
            "required": tool.required_params,
            "optional": tool.optional_params
        }
    
    def _extract_zapier_error_or_question(self, result: Any) -> Optional[str]:
        """
        Extract error or clarification question from Zapier result.
        
        Zapier sometimes returns success=True but with:
        - A clarification question (e.g., "Which calendar?", "Which account?")
        - An error (e.g., authentication errors, missing params)
        
        This method detects such issues so we can handle them appropriately.
        
        Args:
            result: The result from Zapier tool execution
            
        Returns:
            The error/question string if found, None otherwise
        """
        if not result:
            return None
        
        # Handle different result formats
        try:
            import json
            
            # If result is a dict with 'content' (MCP format)
            if isinstance(result, dict):
                # FIRST: Check for top-level isError flag
                if result.get('isError'):
                    # Try to extract error from content
                    content = result.get('content', [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                text = item.get('text', '')
                                try:
                                    parsed = json.loads(text)
                                    if isinstance(parsed, dict) and parsed.get('error'):
                                        return parsed.get('error')
                                except json.JSONDecodeError:
                                    pass
                    return "Zapier returned an error"
                
                content = result.get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text = item.get('text', '')
                            # Try to parse as JSON
                            try:
                                parsed = json.loads(text)
                                if isinstance(parsed, dict):
                                    # Check for isError inside parsed JSON
                                    if parsed.get('isError'):
                                        error = parsed.get('error', 'Zapier returned an error')
                                        return error
                                    # Check for error field with question
                                    error = parsed.get('error', '')
                                    if error and ('Question:' in str(error) or '?' in str(error)):
                                        return error
                                    # Check for question field
                                    question = parsed.get('question', '')
                                    if question:
                                        return question
                            except json.JSONDecodeError:
                                # Check raw text for question patterns
                                if 'Question:' in text or ('?' in text and 'which' in text.lower()):
                                    return text
            
            # If result is a string
            elif isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, dict):
                        if parsed.get('isError'):
                            return parsed.get('error', 'Zapier returned an error')
                        error = parsed.get('error', '')
                        if error and ('Question:' in str(error) or '?' in str(error)):
                            return error
                except json.JSONDecodeError:
                    if 'Question:' in result or ('?' in result and 'which' in result.lower()):
                        return result
            
        except Exception as e:
            logger.debug(f"Error checking for Zapier error/question: {e}")
        
        return None
    
    # Alias for backward compatibility
    def _extract_zapier_question(self, result: Any) -> Optional[str]:
        """Alias for _extract_zapier_error_or_question for backward compatibility."""
        return self._extract_zapier_error_or_question(result)
    
    async def execute(
        self,
        query: str = "",
        user_id: str = None,
        tool_name: str = None,
        params: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a Zapier tool.
        
        Matches the interface used by OptimizedAgent's tool_manager.
        
        Args:
            query: Original user query (for context/logging)
            user_id: User ID (for logging/permissions)
            tool_name: Zapier tool name (with or without prefix)
            params: Tool parameters
            **kwargs: Additional parameters
            
        Returns:
            Result dictionary matching tool_manager format:
            {
                "success": bool,
                "tool": str,
                "result": Any,
                "error": str,
                "execution_time_ms": float,
                "provider": "zapier_mcp"
            }
        """
        if not self._initialized or not self._client:
            return {
                "success": False,
                "error": "ZapierToolManager not initialized",
                "tool": tool_name,
                "provider": "zapier_mcp"
            }
        
        if not tool_name:
            return {
                "success": False,
                "error": "No tool_name provided",
                "tool": None,
                "provider": "zapier_mcp"
            }
        
        # Remove prefix if present
        actual_tool_name = tool_name
        if tool_name.startswith(self.prefix):
            actual_tool_name = tool_name[len(self.prefix):]
        
        logger.info(f"🔧 ZapierToolManager executing: {tool_name}")
        if user_id:
            logger.debug(f"   User: {user_id}")
        if query:
            logger.debug(f"   Query: {query[:100]}...")
        
        # Execute
        try:
            result = await self._client.execute_action(actual_tool_name, params or {})
            
            # UNIVERSAL FIX: Check if Zapier returned a question/error in the result
            # Zapier sometimes returns success=True but with a clarification question
            zapier_question = self._extract_zapier_question(result.result)
            
            if zapier_question:
                # Zapier needs clarification - treat as partial success with question
                logger.warning(f"⚠️ Zapier needs clarification: {zapier_question}")
                return {
                    "success": False,
                    "tool": tool_name,
                    "result": result.result,
                    "error": f"Zapier needs more information: {zapier_question}",
                    "needs_clarification": True,
                    "clarification_question": zapier_question,
                    "execution_time_ms": result.execution_time_ms,
                    "provider": "zapier_mcp"
                }
            
            return {
                "success": result.success,
                "tool": tool_name,
                "result": result.result,
                "error": result.error,
                "execution_time_ms": result.execution_time_ms,
                "provider": "zapier_mcp"
            }
            
        except MCPError as e:
            return {
                "success": False,
                "tool": tool_name,
                "error": str(e),
                "provider": "zapier_mcp"
            }
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return {
                "success": False,
                "tool": tool_name,
                "error": f"Unexpected error: {e}",
                "provider": "zapier_mcp"
            }
    
    async def close(self) -> None:
        """Close Zapier connection"""
        if self._client:
            await self._client.disconnect()
        self._initialized = False
        self._tool_schemas.clear()
        logger.info("✅ ZapierToolManager closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        stats = {
            "initialized": self._initialized,
            "tools_available": len(self._tool_schemas),
            "prefix": self.prefix
        }
        
        if self._client:
            stats["client_stats"] = self._client.get_usage_stats()
        
        return stats


# Helper function for generating tool descriptions for LLM prompts
def get_zapier_tools_prompt(tool_manager: ZapierToolManager, max_tools: int = 20) -> str:
    """
    Generate tool descriptions for LLM analysis prompts.
    
    Args:
        tool_manager: Initialized ZapierToolManager
        max_tools: Maximum number of tools to include
        
    Returns:
        Formatted string for including in LLM prompts
    """
    if not tool_manager.is_initialized:
        return "ZAPIER TOOLS: Not configured"
    
    schemas = tool_manager.get_tool_schemas()
    
    if not schemas:
        return "ZAPIER TOOLS: No tools available"
    
    # Group by category
    by_category: Dict[str, List[Dict]] = {}
    for name, schema in schemas.items():
        cat = schema.get("category", "other")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(schema)
    
    lines = ["ZAPIER TOOLS (via MCP):"]
    lines.append("Use these when user needs to perform actions in external apps.\n")
    
    tool_count = 0
    for category, tools in sorted(by_category.items()):
        if tool_count >= max_tools:
            break
            
        lines.append(f"{category.upper()} TOOLS:")
        for tool in tools[:5]:  # Max 5 per category
            if tool_count >= max_tools:
                break
            
            name = tool["name"]
            desc = tool["description"][:80] if tool["description"] else tool["display_name"]
            required = tool.get("required", [])
            
            lines.append(f"  - {name}: {desc}")
            if required:
                lines.append(f"    Required params: {', '.join(required)}")
            
            tool_count += 1
        lines.append("")
    
    remaining = len(schemas) - tool_count
    if remaining > 0:
        lines.append(f"... and {remaining} more tools available")
    
    return "\n".join(lines)
