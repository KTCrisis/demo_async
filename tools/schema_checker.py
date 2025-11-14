#!/usr/bin/env python3
"""
Schema Registry Health Check - FIXED VERSION
Monitors schema health and reports anomalies
"""

import os
import sys
import requests
import json
from datetime import datetime, timezone
from typing import Dict, List
import argparse

class SchemaHealthChecker:
    def __init__(self, endpoint: str, api_key: str, api_secret: str):
        self.endpoint = endpoint.rstrip('/')
        self.auth = (api_key, api_secret)
        self.issues = []
        self.warnings = []
        self.timeout = 10  # Timeout pour toutes les requÃªtes
    
    def check_all(self) -> Dict:
        """Run all health checks"""
        print("ðŸ” Running Schema Registry Health Checks...\n")
        
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": self.endpoint,
            "checks": {}
        }
        
        # 1. Connectivity
        print("  â†’ Testing connectivity...")
        results["checks"]["connectivity"] = self._check_connectivity()
        
        # 2. Subject count
        print("  â†’ Counting subjects...")
        results["checks"]["subject_count"] = self._check_subject_count()
        
        # 3. Version explosion
        print("  â†’ Checking version counts...")
        results["checks"]["version_explosion"] = self._check_version_explosion()
        
        # 4. Large schemas
        print("  â†’ Checking schema sizes...")
        results["checks"]["large_schemas"] = self._check_large_schemas()
        
        # 5. Compatibility config
        print("  â†’ Checking compatibility configs...")
        results["checks"]["compatibility"] = self._check_compatibility_config()
        
        # 6. Soft-deleted subjects
        print("  â†’ Checking soft-deleted subjects...")
        results["checks"]["soft_deleted"] = self._check_soft_deleted()
        
        # 7. Orphaned references
        print("  â†’ Checking orphaned references...")
        results["checks"]["orphaned_refs"] = self._check_orphaned_references()
        
        # Summary
        results["summary"] = {
            "total_issues": len(self.issues),
            "total_warnings": len(self.warnings),
            "issues": self.issues,
            "warnings": self.warnings,
            "status": "CRITICAL" if self.issues else ("WARNING" if self.warnings else "OK")
        }
        
        return results
    
    def _check_connectivity(self) -> Dict:
        """Test SR connectivity"""
        try:
            response = requests.get(
                f"{self.endpoint}/subjects",
                auth=self.auth,
                timeout=self.timeout
            )
            response.raise_for_status()
            return {"status": "OK", "message": "Schema Registry is reachable"}
        except requests.exceptions.Timeout:
            msg = "Connection timeout (>10s)"
            self.issues.append(f"Connectivity: {msg}")
            return {"status": "CRITICAL", "message": msg}
        except requests.exceptions.ConnectionError as e:
            msg = f"Connection error: {str(e)}"
            self.issues.append(f"Connectivity: {msg}")
            return {"status": "CRITICAL", "message": msg}
        except Exception as e:
            msg = str(e)
            self.issues.append(f"Connectivity: {msg}")
            return {"status": "CRITICAL", "message": msg}
    
    def _check_subject_count(self) -> Dict:
        """Check total number of subjects"""
        try:
            response = requests.get(
                f"{self.endpoint}/subjects",
                auth=self.auth,
                timeout=self.timeout
            )
            response.raise_for_status()
            subjects = response.json()
            count = len(subjects)
            
            status = "OK"
            message = f"Total subjects: {count}"
            
            if count > 1000:
                status = "WARNING"
                self.warnings.append(f"High subject count: {count}")
            elif count > 5000:
                status = "CRITICAL"
                self.issues.append(f"Very high subject count: {count}")
            
            return {"status": status, "count": count, "message": message}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def _check_version_explosion(self) -> Dict:
        """Check for subjects with too many versions"""
        try:
            response = requests.get(
                f"{self.endpoint}/subjects",
                auth=self.auth,
                timeout=self.timeout
            )
            subjects = response.json()
            
            explosions = []
            for subject in subjects:
                try:
                    versions_resp = requests.get(
                        f"{self.endpoint}/subjects/{subject}/versions",
                        auth=self.auth,
                        timeout=self.timeout
                    )
                    versions = versions_resp.json()
                    version_count = len(versions)
                    
                    if version_count > 50:
                        explosions.append({
                            "subject": subject,
                            "versions": version_count
                        })
                        if version_count > 100:
                            self.issues.append(f"{subject}: {version_count} versions")
                        else:
                            self.warnings.append(f"{subject}: {version_count} versions")
                except requests.exceptions.Timeout:
                    print(f"    âš ï¸  Timeout checking versions for {subject}")
                    continue
                except Exception:
                    continue
            
            if explosions:
                return {
                    "status": "WARNING" if not self.issues else "CRITICAL",
                    "explosions": explosions,
                    "message": f"Found {len(explosions)} subjects with >50 versions"
                }
            
            return {"status": "OK", "message": "No version explosions detected"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def _check_large_schemas(self) -> Dict:
        """Check for unusually large schemas"""
        try:
            response = requests.get(
                f"{self.endpoint}/subjects",
                auth=self.auth,
                timeout=self.timeout
            )
            subjects = response.json()
            
            large_schemas = []
            # Limit to first 100 to avoid long checks
            sample_size = min(len(subjects), 100)
            
            for subject in subjects[:sample_size]:
                try:
                    schema_resp = requests.get(
                        f"{self.endpoint}/subjects/{subject}/versions/latest",
                        auth=self.auth,
                        timeout=self.timeout
                    )
                    schema_data = schema_resp.json()
                    schema_str = schema_data.get('schema', '')
                    size_kb = len(schema_str) / 1024
                    
                    if size_kb > 100:  # > 100KB
                        large_schemas.append({
                            "subject": subject,
                            "size_kb": round(size_kb, 2)
                        })
                        self.warnings.append(f"{subject}: {size_kb:.2f} KB")
                except requests.exceptions.Timeout:
                    print(f"    âš ï¸  Timeout checking size for {subject}")
                    continue
                except Exception:
                    continue
            
            if large_schemas:
                return {
                    "status": "WARNING",
                    "large_schemas": large_schemas,
                    "message": f"Found {len(large_schemas)} large schemas (>100KB)"
                }
            
            return {"status": "OK", "message": "No unusually large schemas"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def _check_compatibility_config(self) -> Dict:
        """Check compatibility configuration"""
        try:
            # Global config
            global_resp = requests.get(
                f"{self.endpoint}/config",
                auth=self.auth,
                timeout=self.timeout
            )
            global_config = global_resp.json()
            
            # Subjects with NONE compatibility
            response = requests.get(
                f"{self.endpoint}/subjects",
                auth=self.auth,
                timeout=self.timeout
            )
            subjects = response.json()
            
            none_compat = []
            # Limit to 50 subjects to avoid long checks
            sample_size = min(len(subjects), 50)
            
            for subject in subjects[:sample_size]:
                try:
                    config_resp = requests.get(
                        f"{self.endpoint}/config/{subject}",
                        auth=self.auth,
                        timeout=self.timeout
                    )
                    if config_resp.status_code == 200:
                        config = config_resp.json()
                        if config.get('compatibilityLevel') == 'NONE':
                            none_compat.append(subject)
                except requests.exceptions.Timeout:
                    print(f"    âš ï¸  Timeout checking config for {subject}")
                    continue
                except Exception:
                    continue
            
            if none_compat:
                self.warnings.append(f"{len(none_compat)} subjects with NONE compatibility")
                return {
                    "status": "WARNING",
                    "global_config": global_config,
                    "none_compat_count": len(none_compat),
                    "message": f"{len(none_compat)} subjects with NONE compatibility"
                }
            
            return {
                "status": "OK",
                "global_config": global_config,
                "message": "Compatibility configs look good"
            }
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def _check_soft_deleted(self) -> Dict:
        """Check for soft-deleted subjects"""
        try:
            response = requests.get(
                f"{self.endpoint}/subjects?deleted=true",
                auth=self.auth,
                timeout=self.timeout
            )
            deleted = response.json()
            count = len(deleted)
            
            if count > 0:
                self.warnings.append(f"{count} soft-deleted subjects")
                return {
                    "status": "WARNING",
                    "count": count,
                    "subjects": deleted[:10],  # First 10
                    "message": f"{count} subjects in soft-delete state"
                }
            
            return {"status": "OK", "message": "No soft-deleted subjects"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def _check_orphaned_references(self) -> Dict:
        """Check for schemas with broken references"""
        try:
            response = requests.get(
                f"{self.endpoint}/subjects",
                auth=self.auth,
                timeout=self.timeout
            )
            subjects = response.json()
            
            orphaned = []
            # Limit to 50 subjects
            sample_size = min(len(subjects), 50)
            
            for subject in subjects[:sample_size]:
                try:
                    schema_resp = requests.get(
                        f"{self.endpoint}/subjects/{subject}/versions/latest",
                        auth=self.auth,
                        timeout=self.timeout
                    )
                    schema_data = schema_resp.json()
                    
                    references = schema_data.get('references', [])
                    for ref in references:
                        ref_subject = ref['subject']
                        # Check if referenced subject exists
                        check_resp = requests.get(
                            f"{self.endpoint}/subjects/{ref_subject}/versions",
                            auth=self.auth,
                            timeout=self.timeout
                        )
                        if check_resp.status_code == 404:
                            orphaned.append({
                                "subject": subject,
                                "missing_ref": ref_subject
                            })
                            self.issues.append(f"{subject} â†’ {ref_subject} (missing)")
                except requests.exceptions.Timeout:
                    print(f"    âš ï¸  Timeout checking references for {subject}")
                    continue
                except Exception:
                    continue
            
            if orphaned:
                return {
                    "status": "CRITICAL",
                    "orphaned": orphaned,
                    "message": f"Found {len(orphaned)} broken references"
                }
            
            return {"status": "OK", "message": "No orphaned references"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    def print_report(self, results: Dict):
        """Print formatted report"""
        print("\n" + "="*60)
        print("ðŸ“Š SCHEMA REGISTRY HEALTH REPORT")
        print("="*60)
        print(f"Timestamp: {results['timestamp']}")
        print(f"Endpoint: {results['endpoint']}")
        print(f"Status: {results['summary']['status']}")
        print()
        
        for check_name, check_result in results['checks'].items():
            status_emoji = {
                "OK": "âœ…",
                "WARNING": "âš ï¸",
                "CRITICAL": "ðŸš¨",
                "ERROR": "âŒ"
            }.get(check_result.get('status', 'ERROR'), "â“")
            
            print(f"{status_emoji} {check_name.replace('_', ' ').title()}")
            print(f"   {check_result.get('message', 'No message')}")
            print()
        
        if results['summary']['issues']:
            print("ðŸš¨ CRITICAL ISSUES:")
            for issue in results['summary']['issues']:
                print(f"   - {issue}")
            print()
        
        if results['summary']['warnings']:
            print("âš ï¸  WARNINGS:")
            for warning in results['summary']['warnings']:
                print(f"   - {warning}")
            print()
        
        print("="*60)

def main():
    parser = argparse.ArgumentParser(description="Schema Registry Health Check")
    parser.add_argument('--env', required=True, help='Environment suffix (dev, sta, int, ope, debug)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()
    
    # Get credentials
    api_key = os.getenv(f"TF_VAR_kafka_schema_registry_api_key_{args.env}")
    api_secret = os.getenv(f"TF_VAR_kafka_schema_registry_api_secret_{args.env}")
    endpoint = os.getenv(f"TF_VAR_schema_registry_rest_endpoint_{args.env}")
    
    if not all([api_key, api_secret, endpoint]):
        print(f"âŒ Missing credentials for env: {args.env}")
        print(f"   Expected variables:")
        print(f"   - TF_VAR_kafka_schema_registry_api_key_{args.env}")
        print(f"   - TF_VAR_kafka_schema_registry_api_secret_{args.env}")
        print(f"   - TF_VAR_schema_registry_rest_endpoint_{args.env}")
        sys.exit(1)
    
    print(f"ðŸ”§ Testing Schema Registry: {endpoint}\n")
    
    # Run checks
    try:
        checker = SchemaHealthChecker(endpoint, api_key, api_secret)
        results = checker.check_all()
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            checker.print_report(results)
        
        # Exit code based on status
        if results['summary']['status'] == 'CRITICAL':
            sys.exit(2)
        elif results['summary']['status'] == 'WARNING':
            sys.exit(1)
        else:
            sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nâš ï¸  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nâŒ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()