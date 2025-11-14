#!/usr/bin/env python3
"""
Schema Registry Purger
Handles deletion operations for Schema Registry subjects
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime, timezone


class SchemaPurger:
    def __init__(self, endpoint: str, api_key: str, api_secret: str):
        self.endpoint = endpoint.rstrip('/')
        self.auth = (api_key, api_secret)
        self.timeout = 10
    
    def get_all_subjects(self, include_deleted: bool = False) -> List[str]:
        """Get all subjects from Schema Registry"""
        try:
            url = f"{self.endpoint}/subjects"
            if include_deleted:
                url += "?deleted=true"
            
            response = requests.get(url, auth=self.auth, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to get subjects: {str(e)}")
    
    def get_subject_details(self, subject: str) -> Dict:
        """Get detailed information about a subject"""
        try:
            # Get versions
            versions_resp = requests.get(
                f"{self.endpoint}/subjects/{subject}/versions",
                auth=self.auth,
                timeout=self.timeout
            )
            versions = versions_resp.json() if versions_resp.status_code == 200 else []
            
            # Get latest schema
            latest_resp = requests.get(
                f"{self.endpoint}/subjects/{subject}/versions/latest",
                auth=self.auth,
                timeout=self.timeout
            )
            latest = latest_resp.json() if latest_resp.status_code == 200 else {}
            
            schema_str = latest.get('schema', '')
            size_kb = len(schema_str) / 1024
            
            return {
                "subject": subject,
                "versions": versions,
                "version_count": len(versions),
                "latest_version": latest.get('version'),
                "schema_type": latest.get('schemaType', 'AVRO'),
                "size_kb": round(size_kb, 2),
                "id": latest.get('id')
            }
        except Exception as e:
            return {
                "subject": subject,
                "error": str(e)
            }
    
    def soft_delete_subject(self, subject: str) -> Dict:
        """Soft delete a subject (can be restored)"""
        try:
            response = requests.delete(
                f"{self.endpoint}/subjects/{subject}",
                auth=self.auth,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                versions = response.json()
                return {
                    "success": True,
                    "subject": subject,
                    "deleted_versions": versions,
                    "message": f"Soft-deleted {len(versions)} versions"
                }
            else:
                return {
                    "success": False,
                    "subject": subject,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "success": False,
                "subject": subject,
                "error": str(e)
            }
    
    def hard_delete_subject(self, subject: str) -> Dict:
        """Hard delete a subject (permanent - cannot be restored)"""
        try:
            # First soft delete if not already deleted
            soft_delete_resp = requests.delete(
                f"{self.endpoint}/subjects/{subject}",
                auth=self.auth,
                timeout=self.timeout
            )
            
            # Then hard delete
            response = requests.delete(
                f"{self.endpoint}/subjects/{subject}?permanent=true",
                auth=self.auth,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                versions = response.json()
                return {
                    "success": True,
                    "subject": subject,
                    "deleted_versions": versions,
                    "message": f"Permanently deleted {len(versions)} versions"
                }
            else:
                return {
                    "success": False,
                    "subject": subject,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "success": False,
                "subject": subject,
                "error": str(e)
            }
    
    def delete_subject_version(self, subject: str, version: str) -> Dict:
        """Delete a specific version of a subject"""
        try:
            response = requests.delete(
                f"{self.endpoint}/subjects/{subject}/versions/{version}",
                auth=self.auth,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "subject": subject,
                    "version": version,
                    "message": f"Deleted version {version}"
                }
            else:
                return {
                    "success": False,
                    "subject": subject,
                    "version": version,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "success": False,
                "subject": subject,
                "version": version,
                "error": str(e)
            }
    
    def bulk_soft_delete(self, subjects: List[str]) -> Dict:
        """Soft delete multiple subjects"""
        results = {
            "total": len(subjects),
            "successful": [],
            "failed": [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        for subject in subjects:
            result = self.soft_delete_subject(subject)
            if result["success"]:
                results["successful"].append(result)
            else:
                results["failed"].append(result)
        
        results["success_count"] = len(results["successful"])
        results["failure_count"] = len(results["failed"])
        
        return results
    
    def bulk_hard_delete(self, subjects: List[str]) -> Dict:
        """Hard delete multiple subjects"""
        results = {
            "total": len(subjects),
            "successful": [],
            "failed": [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        for subject in subjects:
            result = self.hard_delete_subject(subject)
            if result["success"]:
                results["successful"].append(result)
            else:
                results["failed"].append(result)
        
        results["success_count"] = len(results["successful"])
        results["failure_count"] = len(results["failed"])
        
        return results
    
    def purge_soft_deleted(self) -> Dict:
        """Permanently delete all soft-deleted subjects"""
        try:
            # Get all soft-deleted subjects
            soft_deleted = self.get_all_subjects(include_deleted=True)
            active = self.get_all_subjects(include_deleted=False)
            
            # Find subjects that are deleted (in first list but not second)
            deleted_subjects = [s for s in soft_deleted if s not in active]
            
            if not deleted_subjects:
                return {
                    "success": True,
                    "message": "No soft-deleted subjects found",
                    "count": 0
                }
            
            # Hard delete all soft-deleted subjects
            return self.bulk_hard_delete(deleted_subjects)
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_subjects_by_filter(self, 
                               min_versions: Optional[int] = None,
                               pattern: Optional[str] = None) -> List[str]:
        """Get subjects matching filters"""
        try:
            all_subjects = self.get_all_subjects()
            filtered = []
            
            for subject in all_subjects:
                include = True
                
                # Filter by version count
                if min_versions is not None:
                    details = self.get_subject_details(subject)
                    if details.get("version_count", 0) < min_versions:
                        include = False
                
                # Filter by pattern (simple contains for now)
                if pattern and pattern not in subject:
                    include = False
                
                if include:
                    filtered.append(subject)
            
            return filtered
        except Exception as e:
            raise Exception(f"Failed to filter subjects: {str(e)}")