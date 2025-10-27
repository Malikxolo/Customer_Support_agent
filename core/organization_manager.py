"""
Organization Management - Simple JSON-based implementation
Handles org creation, joining, and permission checks
"""

import os
import json
import random
import string
from datetime import datetime
from typing import Dict, Any, Optional, List


PERMISSIONS = {
    "owner": {
        # Collections
        "upload_documents": True,
        "edit_collection": True,
        "delete_collection": True,
        
        # Teams
        "create_team": True,
        "manage_teams": True,
        "delete_team": True,
        "view_teams": True,
        
        # Members
        "assign_members": True,
        "remove_members": True,
        "view_members": True,
        
        # Organization
        "view_invite_code": True,
        "regenerate_invite": True,
        "leave_org": True,
        "delete_org": True,
        
        # Query
        "select_team_for_query": True,
    },
    
    "team_admin": {
        # Collections (THEIR TEAM ONLY)
        "upload_documents": True,
        "edit_collection": True,
        "delete_collection": True,
        
        # Teams
        "create_team": False,
        "manage_teams": False,
        "delete_team": False,
        "view_teams": True,
        
        # Members (THEIR TEAM ONLY)
        "assign_members": True,
        "remove_members": True,
        "view_members": True,
        
        # Organization
        "view_invite_code": False,
        "regenerate_invite": False,
        "leave_org": True,
        "delete_org": False,
        
        # Query
        "select_team_for_query": False,
    },
    
    "member": {
        # Collections
        "upload_documents": False,
        "edit_collection": False,
        "delete_collection": False,
        
        # Teams
        "create_team": False,
        "manage_teams": False,
        "delete_team": False,
        "view_teams": True,
        
        # Members
        "assign_members": False,
        "remove_members": False,
        "view_members": True,
        
        # Organization
        "view_invite_code": False,
        "regenerate_invite": False,
        "leave_org": True,
        "delete_org": False,
        
        # Query
        "select_team_for_query": False,
    },
    
    "viewer": {
        # Collections
        "upload_documents": False,
        "edit_collection": False,
        "delete_collection": False,
        
        # Teams
        "create_team": False,
        "manage_teams": False,
        "delete_team": False,
        "view_teams": False,
        
        # Members
        "assign_members": False,
        "remove_members": False,
        "view_members": False,
        
        # Organization
        "view_invite_code": False,
        "regenerate_invite": False,
        "leave_org": True,
        "delete_org": False,
        
        # Query
        "select_team_for_query": False,
    }
}

class OrganizationManager:
    """Manage organizations using JSON file storage"""
    
    def __init__(self, file_path: str = "organizations.json"):
        self.file_path = file_path
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create organizations.json if it doesn't exist"""
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({}, f, indent=2)
    
    def _load_organizations(self) -> Dict[str, Any]:
        """Load all organizations from JSON"""
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading organizations: {e}")
            return {}
    
    def _save_organizations(self, orgs: Dict[str, Any]):
        """Save organizations to JSON"""
        try:
            with open(self.file_path, 'w') as f:
                json.dump(orgs, f, indent=2)
        except Exception as e:
            print(f"Error saving organizations: {e}")
    
    def _generate_invite_code(self, org_name: str) -> str:
        """Generate unique 8-character invite code"""
        # Safe characters (no confusing ones: O, I, L, 0, 1)
        chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
        
        # Prefix with org initials (3 chars max)
        words = org_name.upper().split()
        prefix = ''.join([w[0] for w in words[:3]])[:3]
        
        # Random suffix
        suffix = ''.join(random.choices(chars, k=5))
        
        code = f"{prefix}{suffix}"
        
        # Ensure uniqueness
        orgs = self._load_organizations()
        while self._code_exists(code, orgs):
            suffix = ''.join(random.choices(chars, k=5))
            code = f"{prefix}{suffix}"
        
        return code
    
    def _code_exists(self, code: str, orgs: Dict[str, Any]) -> bool:
        """Check if invite code already exists"""
        for org in orgs.values():
            if org.get("invite_code") == code:
                return True
        return False
    
    def _generate_org_id(self, org_name: str) -> str:
        """Generate org_id from org name"""
        # Convert to lowercase, replace spaces with underscore
        org_id = org_name.lower().replace(" ", "_")
        # Remove special characters
        org_id = ''.join(c for c in org_id if c.isalnum() or c == '_')
        return f"org_{org_id}"
    
    def create_organization(
        self, 
        org_name: str, 
        creator_name: str, 
        creator_id: str
    ) -> Dict[str, Any]:
        """
        Create a new organization
        
        Args:
            org_name: Name of the organization
            creator_name: Display name of creator
            creator_id: Unique user ID (from session)
        
        Returns:
            {
                "success": bool,
                "org_id": str,
                "invite_code": str,
                "error": str (if failed)
            }
        """
        try:
            orgs = self._load_organizations()
            
            # Generate IDs
            org_id = self._generate_org_id(org_name)
            
            # Check if org already exists
            if org_id in orgs:
                return {
                    "success": False,
                    "error": f"Organization '{org_name}' already exists"
                }
            
            # Generate invite code
            invite_code = self._generate_invite_code(org_name)
            
            # Create organization structure
            org_data = {
                "org_id": org_id,
                "org_name": org_name,
                "invite_code": invite_code,
                "owner_id": creator_id,  
                "created_at": datetime.now().isoformat(),
                "teams": {},  
                "members": {
                    creator_id: {
                        "name": creator_name,
                        "role": "owner",  
                        "team_id": None,  
                        "joined_at": datetime.now().isoformat()
                    }
                }
            }

            
            # Save to JSON
            orgs[org_id] = org_data
            self._save_organizations(orgs)
            
            return {
                "success": True,
                "org_id": org_id,
                "org_name": org_name,
                "invite_code": invite_code,
                "role": "owner"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create organization: {str(e)}"
            }
    
    def join_organization(
        self, 
        invite_code: str, 
        user_name: str, 
        user_id: str
    ) -> Dict[str, Any]:
        """
        Join an organization using invite code
        
        Args:
            invite_code: 8-character invite code
            user_name: Display name of user
            user_id: Unique user ID (from session)
        
        Returns:
            {
                "success": bool,
                "org_id": str,
                "org_name": str,
                "role": "viewer",
                "error": str (if failed)
            }
        """
        try:
            orgs = self._load_organizations()
            
            # Find org by invite code
            target_org_id = None
            for org_id, org_data in orgs.items():
                if org_data.get("invite_code") == invite_code.upper():
                    target_org_id = org_id
                    break
            
            if not target_org_id:
                return {
                    "success": False,
                    "error": f"Invalid invite code: {invite_code}"
                }
            
            # Get organization
            org = orgs[target_org_id]
            
            # Check if user already a member
            if user_id in org["members"]:
                return {
                    "success": True,
                    "org_id": target_org_id,
                    "org_name": org["org_name"],
                    "role": org["members"][user_id]["role"],
                    "message": "You are already a member of this organization"
                }
            
            # Add user as member (unassigned)
            org["members"][user_id] = {
                "name": user_name,
                "role": "viewer",  
                "team_id": None,   
                "joined_at": datetime.now().isoformat()
            }
            
            # Save updated org
            orgs[target_org_id] = org
            self._save_organizations(orgs)
            
            return {
                "success": True,
                "org_id": target_org_id,
                "org_name": org["org_name"],
                "role": "viewer" 
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to join organization: {str(e)}"
            }
    
    def get_user_role(self, org_id: str, user_id: str) -> Optional[str]:
        """Get user's role in organization"""
        try:
            orgs = self._load_organizations()
            if org_id in orgs:
                members = orgs[org_id].get("members", {})
                if user_id in members:
                    return members[user_id].get("role")
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None
    
    def check_permission(self, org_id: str, user_id: str, action: str) -> bool:
        """
        Check if user has permission for action
        
        Args:
            org_id: Organization ID
            user_id: User ID
            action: Action from PERMISSIONS dict (e.g., 'upload_documents')
        
        Returns:
            bool: True if user has permission
        """
        role = self.get_user_role(org_id, user_id)
        
        if not role:
            return False
        
        # Get role permissions from PERMISSIONS dict
        role_permissions = PERMISSIONS.get(role, {})
        return role_permissions.get(action, False)

    def get_organization(self, org_id: str) -> Optional[Dict[str, Any]]:
        """Get organization data"""
        try:
            orgs = self._load_organizations()
            return orgs.get(org_id)
        except Exception as e:
            print(f"Error getting organization: {e}")
            return None
    
    def get_organization_by_code(self, invite_code: str) -> Optional[Dict[str, Any]]:
        """Find organization by invite code"""
        try:
            orgs = self._load_organizations()
            for org_id, org_data in orgs.items():
                if org_data.get("invite_code") == invite_code.upper():
                    return org_data
            return None
        except Exception as e:
            print(f"Error finding organization: {e}")
            return None
    
    def get_member_count(self, org_id: str) -> int:
        """Get number of members in organization"""
        org = self.get_organization(org_id)
        if org:
            return len(org.get("members", {}))
        return 0
    
    def get_members(self, org_id: str) -> List[Dict[str, Any]]:
        """Get list of members with details"""
        org = self.get_organization(org_id)
        if org:
            members = []
            for user_id, member_data in org.get("members", {}).items():
                members.append({
                    "user_id": user_id,
                    "name": member_data.get("name"),
                    "role": member_data.get("role"),
                    "joined_at": member_data.get("joined_at")
                })
            return members
        return []
    def transfer_admin(self, org_id: str, old_admin_id: str, new_admin_id: str):
        """Transfer admin role to another member"""
        orgs = self._load_organizations()
        
        if org_id in orgs:
            # Remove old admin from members (they're leaving)
            if old_admin_id in orgs[org_id]["members"]:
                del orgs[org_id]["members"][old_admin_id]
            
            # Promote new admin
            if new_admin_id in orgs[org_id]["members"]:
                orgs[org_id]["members"][new_admin_id]["role"] = "owner"

            
            self._save_organizations(orgs)
    
    def remove_member(self, org_id: str, user_id: str):
        """Remove member from organization"""
        orgs = self._load_organizations()
        
        if org_id in orgs and user_id in orgs[org_id]["members"]:
            del orgs[org_id]["members"][user_id]
            self._save_organizations(orgs)
    
    def delete_organization(self, org_id: str):
        """Delete organization completely"""
        orgs = self._load_organizations()
        
        if org_id in orgs:
            del orgs[org_id]
            self._save_organizations(orgs)
            
    def create_team(self, org_id: str, team_name: str, owner_id: str) -> Dict[str, Any]:
        """Create a new team within organization"""
        try:
            orgs = self._load_organizations()
            
            if org_id not in orgs:
                return {"success": False, "error": "Organization not found"}
            
            # Check if owner
            if orgs[org_id]["owner_id"] != owner_id:
                return {"success": False, "error": "Only owner can create teams"}
            
            # Generate team ID
            team_id = f"team_{team_name.lower().replace(' ', '_')}"
            
            # Check if team exists
            if "teams" not in orgs[org_id]:
                orgs[org_id]["teams"] = {}
            
            if team_id in orgs[org_id]["teams"]:
                return {"success": False, "error": "Team already exists"}
            
            # Create team
            orgs[org_id]["teams"][team_id] = {
                "team_id": team_id,
                "team_name": team_name,
                "team_admin_id": None,  # Not assigned yet
                "created_at": datetime.now().isoformat()
            }
            
            self._save_organizations(orgs)
            
            return {
                "success": True,
                "team_id": team_id,
                "team_name": team_name
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_teams(self, org_id: str) -> List[Dict[str, Any]]:
        """Get all teams in organization"""
        try:
            orgs = self._load_organizations()
            if org_id in orgs:
                teams = orgs[org_id].get("teams", {})
                return [team_data for team_data in teams.values()]
            return []
        except Exception as e:
            print(f"Error getting teams: {e}")
            return []
    
    def assign_team_admin(self, org_id: str, team_id: str, user_id: str, owner_id: str) -> Dict[str, Any]:
        """Assign team admin"""
        try:
            orgs = self._load_organizations()
            
            if org_id not in orgs:
                return {"success": False, "error": "Organization not found"}
            
            # Check if owner
            if orgs[org_id]["owner_id"] != owner_id:
                return {"success": False, "error": "Only owner can assign team admin"}
            
            # Check if team exists
            if team_id not in orgs[org_id].get("teams", {}):
                return {"success": False, "error": "Team not found"}
            
            # Check if user in org
            if user_id not in orgs[org_id]["members"]:
                return {"success": False, "error": "User not in organization"}
            
            # Assign team admin
            orgs[org_id]["teams"][team_id]["team_admin_id"] = user_id
            orgs[org_id]["members"][user_id]["role"] = "team_admin"
            orgs[org_id]["members"][user_id]["team_id"] = team_id
            
            self._save_organizations(orgs)
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def add_member_to_team(self, org_id: str, team_id: str, user_id: str, by_user_id: str) -> Dict[str, Any]:
        """Add member to team (by owner or team admin)"""
        try:
            orgs = self._load_organizations()
            
            if org_id not in orgs:
                return {"success": False, "error": "Organization not found"}
            
            org = orgs[org_id]
            
            # Check permission (owner or team admin)
            is_owner = org["owner_id"] == by_user_id
            is_team_admin = (team_id in org.get("teams", {}) and 
                           org["teams"][team_id].get("team_admin_id") == by_user_id)
            
            if not (is_owner or is_team_admin):
                return {"success": False, "error": "Permission denied"}
            
            # Check if user exists
            if user_id not in org["members"]:
                return {"success": False, "error": "User not in organization"}
            
            # Check if team exists
            if team_id not in org.get("teams", {}):
                return {"success": False, "error": "Team not found"}
            
            # Add to team
            org["members"][user_id]["team_id"] = team_id

            # Auto-promote viewer to member when assigned
            if org["members"][user_id]["role"] == "viewer":
                org["members"][user_id]["role"] = "member"
            elif org["members"][user_id]["role"] not in ["owner", "team_admin"]:
                org["members"][user_id]["role"] = "member"

            
            self._save_organizations(orgs)
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def remove_member_from_team(self, org_id: str, team_id: str, user_id: str, by_user_id: str) -> Dict[str, Any]:
        """Remove member from team (by owner or team admin)"""
        try:
            orgs = self._load_organizations()
            
            if org_id not in orgs:
                return {"success": False, "error": "Organization not found"}
            
            org = orgs[org_id]
            
            # Check permission
            is_owner = org["owner_id"] == by_user_id
            is_team_admin = (team_id in org.get("teams", {}) and 
                           org["teams"][team_id].get("team_admin_id") == by_user_id)
            
            if not (is_owner or is_team_admin):
                return {"success": False, "error": "Permission denied"}
            
            # Remove from team
            if user_id in org["members"]:
                org["members"][user_id]["team_id"] = None
                # Demote based on current role
                if org["members"][user_id]["role"] == "team_admin":
                    org["members"][user_id]["role"] = "viewer"  
                elif org["members"][user_id]["role"] == "member":
                    org["members"][user_id]["role"] = "viewer"  
            
            self._save_organizations(orgs)
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_unassigned_members(self, org_id: str) -> List[Dict[str, Any]]:
        """Get members not assigned to any team"""
        try:
            orgs = self._load_organizations()
            if org_id in orgs:
                members = []
                for user_id, member_data in orgs[org_id].get("members", {}).items():
                    if member_data.get("team_id") is None and member_data.get("role") != "owner":
                        members.append({
                            "user_id": user_id,
                            "name": member_data.get("name"),
                            "role": member_data.get("role")
                        })
                return members
            return []
        except Exception as e:
            print(f"Error getting unassigned members: {e}")
            return []
    
    def get_team_members(self, org_id: str, team_id: str) -> List[Dict[str, Any]]:
        """Get all members of a team"""
        try:
            orgs = self._load_organizations()
            if org_id in orgs:
                members = []
                for user_id, member_data in orgs[org_id].get("members", {}).items():
                    if member_data.get("team_id") == team_id:
                        members.append({
                            "user_id": user_id,
                            "name": member_data.get("name"),
                            "role": member_data.get("role")
                        })
                return members
            return []
        except Exception as e:
            print(f"Error getting team members: {e}")
            return []
    
    def delete_team(self, org_id: str, team_id: str, owner_id: str) -> Dict[str, Any]:
        """Delete team (only if empty)"""
        try:
            orgs = self._load_organizations()
            
            if org_id not in orgs:
                return {"success": False, "error": "Organization not found"}
            
            # Check if owner
            if orgs[org_id]["owner_id"] != owner_id:
                return {"success": False, "error": "Only owner can delete teams"}
            
            # Check if team has members
            team_members = self.get_team_members(org_id, team_id)
            if team_members:
                return {"success": False, "error": f"Team has {len(team_members)} members. Remove them first."}
            
            # Delete team
            if team_id in orgs[org_id].get("teams", {}):
                del orgs[org_id]["teams"][team_id]
            
            self._save_organizations(orgs)
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# Global instance
org_manager = OrganizationManager()


# Convenience functions
def create_organization(org_name: str, creator_name: str, creator_id: str) -> Dict[str, Any]:
    """Create new organization"""
    return org_manager.create_organization(org_name, creator_name, creator_id)


def join_organization(invite_code: str, user_name: str, user_id: str) -> Dict[str, Any]:
    """Join organization with invite code"""
    return org_manager.join_organization(invite_code, user_name, user_id)


def check_permission(org_id: str, user_id: str, action: str) -> bool:
    """Check if user can perform action"""
    return org_manager.check_permission(org_id, user_id, action)


def get_organization(org_id: str) -> Optional[Dict[str, Any]]:
    """Get organization data"""
    return org_manager.get_organization(org_id)

