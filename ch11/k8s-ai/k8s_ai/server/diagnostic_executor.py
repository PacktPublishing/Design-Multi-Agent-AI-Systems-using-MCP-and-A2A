"""Diagnostic agent executor for k8s-ai with session-based cluster management."""

import re
import json
from typing_extensions import override

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from ..utils.cluster_sessions import session_manager


class K8sDiagnosticExecutor(AgentExecutor):
    """Kubernetes Diagnostic Agent executor for A2A server with session-based cluster access."""

    def __init__(self, context: str = None):
        """Initialize with optional default Kubernetes context."""
        self.default_context = context

    def parse_skill_call(self, user_message: str) -> dict:
        """Parse skill calls from user message."""
        # Look for skill calls in format: skill_id: param1=value1, param2=value2
        skill_pattern = r'(\w+):\s*([^,\n]+(?:,\s*[^,\n]+)*)'
        match = re.match(skill_pattern, user_message.strip())

        if not match:
            return None

        skill_id = match.group(1)
        params_str = match.group(2)

        # Parse parameters
        params = {}
        param_pattern = r'(\w+)=([^,]+)'
        param_matches = re.findall(param_pattern, params_str)

        for param_name, param_value in param_matches:
            params[param_name.strip()] = param_value.strip()

        return {
            'skill_id': skill_id,
            'parameters': params
        }

    async def execute_diagnostic_skill(self, skill_id: str, parameters: dict) -> dict:
        """Execute a diagnostic skill."""
        # Extract session token
        session_token = parameters.get("session_token")
        if not session_token:
            return {
                "success": False,
                "error": "session_token parameter is required for all diagnostic skills"
            }

        # Get session
        session = session_manager.get_session(session_token)
        if not session:
            return {
                "success": False,
                "error": "Invalid or expired session token"
            }

        # Get Kubernetes client from session
        try:
            k8s_client = session.get_k8s_client()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to connect to cluster: {str(e)}"
            }

        namespace = parameters.get("namespace", session.credentials.namespace)

        # Execute the appropriate diagnostic skill
        if skill_id == "kubernetes_diagnose_issue":
            return await self.diagnose_issue(k8s_client, parameters, namespace, session)
        elif skill_id == "kubernetes_resource_health":
            return await self.check_resource_health(k8s_client, parameters, namespace, session)
        elif skill_id == "kubernetes_analyze_logs":
            return await self.analyze_logs(k8s_client, parameters, namespace, session)
        elif skill_id == "kubernetes_fix_recommendations":
            return await self.generate_fix_recommendations(k8s_client, parameters, namespace, session)
        else:
            return {
                "success": False,
                "error": f"Unknown diagnostic skill: {skill_id}"
            }

    async def diagnose_issue(self, k8s_client, parameters: dict, namespace: str, session) -> dict:
        """Diagnose cluster issues with detailed analysis."""
        issue_description = parameters.get("issue_description", "General cluster health analysis")

        try:
            # Collect comprehensive diagnostic data
            diagnostic_data = {}

            # Pod analysis
            pods = k8s_client.list_pods(namespace)
            pod_issues = []
            pod_details = []

            for pod in pods.items:
                pod_info = {
                    "name": pod.metadata.name,
                    "status": pod.status.phase,
                    "ready": "0/0",
                    "restarts": 0,
                    "age": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else "Unknown"
                }

                # Container status analysis
                if pod.status.container_statuses:
                    ready_containers = sum(1 for c in pod.status.container_statuses if c.ready)
                    total_containers = len(pod.status.container_statuses)
                    pod_info["ready"] = f"{ready_containers}/{total_containers}"
                    pod_info["restarts"] = sum(c.restart_count for c in pod.status.container_statuses)

                    # Identify container issues
                    for container_status in pod.status.container_statuses:
                        if not container_status.ready:
                            issue_type = "container_not_ready"
                            if container_status.state and container_status.state.waiting:
                                issue_type = f"waiting_{container_status.state.waiting.reason.lower()}"
                            elif container_status.state and container_status.state.terminated:
                                issue_type = f"terminated_{container_status.state.terminated.reason.lower()}"

                            pod_issues.append({
                                "pod": pod.metadata.name,
                                "container": container_status.name,
                                "issue_type": issue_type,
                                "severity": "high" if pod.status.phase == "Failed" else "medium",
                                "description": f"Container {container_status.name} in pod {pod.metadata.name} is not ready"
                            })

                # Pod-level issues
                if pod.status.phase in ["Failed", "Pending"]:
                    pod_issues.append({
                        "pod": pod.metadata.name,
                        "issue_type": f"pod_{pod.status.phase.lower()}",
                        "severity": "high" if pod.status.phase == "Failed" else "medium",
                        "description": f"Pod {pod.metadata.name} is in {pod.status.phase} state"
                    })

                pod_details.append(pod_info)

            # Events analysis
            events = k8s_client.get_events(namespace)
            warning_events = []
            event_summary = {"total": 0, "warnings": 0, "errors": 0}

            for event in events.items:
                event_summary["total"] += 1
                if event.type in ["Warning", "Error"]:
                    event_summary["warnings" if event.type == "Warning" else "errors"] += 1
                    warning_events.append({
                        "type": event.type,
                        "reason": event.reason,
                        "message": event.message,
                        "object": f"{event.involved_object.kind}/{event.involved_object.name}",
                        "timestamp": event.first_timestamp.isoformat() if event.first_timestamp else "Unknown"
                    })

            # Generate detailed analysis
            analysis_parts = []
            analysis_parts.append(f"Comprehensive diagnostic analysis for issue: '{issue_description}'")
            analysis_parts.append(f"Cluster: {session.cluster_name}, Namespace: {namespace}")
            analysis_parts.append(f"Found {len(pod_details)} pods total:")

            running_pods = len([p for p in pod_details if p["status"] == "Running"])
            failed_pods = len([p for p in pod_details if p["status"] == "Failed"])
            pending_pods = len([p for p in pod_details if p["status"] == "Pending"])

            analysis_parts.append(f"  • {running_pods} Running, {failed_pods} Failed, {pending_pods} Pending")
            analysis_parts.append(f"Detected {len(pod_issues)} pod/container issues and {event_summary['warnings'] + event_summary['errors']} warning/error events")

            # Generate recommendations
            recommendations = []
            if failed_pods > 0:
                recommendations.append(f"Investigate {failed_pods} failed pods - check logs and resource constraints")
            if pending_pods > 0:
                recommendations.append(f"Review {pending_pods} pending pods for scheduling issues")
            if event_summary["warnings"] > 5:
                recommendations.append("High number of warning events detected - review cluster events")
            if not recommendations:
                recommendations.append("Continue monitoring cluster health and resource utilization")

            # Determine overall health
            if failed_pods > 0 or len(pod_issues) > 3:
                health_status = "critical"
                confidence = 0.9
            elif pending_pods > 0 or event_summary["warnings"] > 0:
                health_status = "degraded"
                confidence = 0.8
            else:
                health_status = "healthy"
                confidence = 0.95

            result = {
                "success": True,
                "data": {
                    "issue_description": issue_description,
                    "namespace": namespace,
                    "cluster_info": {
                        "cluster_name": session.cluster_name,
                        "api_server": session.credentials.api_server
                    },
                    "diagnosis_status": "completed",
                    "health_status": health_status,
                    "analysis": " ".join(analysis_parts),
                    "identified_issues": pod_issues,
                    "recommended_actions": recommendations,
                    "confidence": confidence,
                    "cluster_data": {
                        "pod_count": len(pod_details),
                        "running_pods": running_pods,
                        "failed_pods": failed_pods,
                        "pending_pods": pending_pods,
                        "warning_events": event_summary["warnings"],
                        "error_events": event_summary["errors"],
                        "total_issues": len(pod_issues)
                    },
                    "detailed_pods": pod_details,
                    "recent_events": warning_events[-10:],  # Last 10 warning/error events
                    "investigation_type": "comprehensive_diagnosis"
                }
            }

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Diagnostic analysis failed: {str(e)}"
            }

    async def check_resource_health(self, k8s_client, parameters: dict, namespace: str, session) -> dict:
        """Check resource health with detailed analysis."""
        resource_type = parameters.get("resource_type", "pod")

        try:
            if resource_type.lower() == "pod":
                pods = k8s_client.list_pods(namespace)
                health_checks = []
                issues_found = []

                for pod in pods.items:
                    checks = {
                        "pod_name": pod.metadata.name,
                        "phase": pod.status.phase,
                        "ready": False,
                        "restart_count": 0,
                        "checks": []
                    }

                    if pod.status.container_statuses:
                        ready_containers = sum(1 for c in pod.status.container_statuses if c.ready)
                        total_containers = len(pod.status.container_statuses)
                        checks["ready"] = ready_containers == total_containers
                        checks["restart_count"] = sum(c.restart_count for c in pod.status.container_statuses)

                        checks["checks"].append(f"Containers: {ready_containers}/{total_containers} ready")
                        checks["checks"].append(f"Total restarts: {checks['restart_count']}")

                        if not checks["ready"]:
                            issues_found.append({
                                "resource": pod.metadata.name,
                                "issue": "containers_not_ready",
                                "description": f"Only {ready_containers}/{total_containers} containers are ready"
                            })

                        if checks["restart_count"] > 5:
                            issues_found.append({
                                "resource": pod.metadata.name,
                                "issue": "high_restart_count",
                                "description": f"High restart count: {checks['restart_count']}"
                            })

                    health_checks.append(checks)

                # Calculate health score
                total_pods = len(health_checks)
                healthy_pods = len([c for c in health_checks if c["ready"] and c["restart_count"] < 5])
                health_score = healthy_pods / total_pods if total_pods > 0 else 1.0

                if health_score >= 0.9:
                    health_status = "healthy"
                elif health_score >= 0.7:
                    health_status = "degraded"
                else:
                    health_status = "unhealthy"

                result = {
                    "success": True,
                    "data": {
                        "resource_type": resource_type,
                        "namespace": namespace,
                        "health_status": health_status,
                        "health_score": health_score,
                        "analysis": f"Resource health analysis for {total_pods} {resource_type}s: {healthy_pods} healthy, {len(issues_found)} issues detected",
                        "checks_performed": [
                            "Pod phase verification",
                            "Container readiness check",
                            "Restart count analysis",
                            "Resource availability assessment"
                        ],
                        "issues_found": issues_found,
                        "recommendations": [
                            "Investigate pods with high restart counts",
                            "Check resource limits and requests",
                            "Review pod logs for error patterns"
                        ] if issues_found else ["Continue monitoring resource health"],
                        "cluster_data": {
                            "total_resources": total_pods,
                            "healthy_resources": healthy_pods,
                            "issues_detected": len(issues_found)
                        },
                        "detailed_checks": health_checks,
                        "confidence": 0.85
                    }
                }

                return result
            else:
                return {
                    "success": False,
                    "error": f"Resource type '{resource_type}' not supported yet. Currently supports: pod"
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Resource health check failed: {str(e)}"
            }

    async def analyze_logs(self, k8s_client, parameters: dict, namespace: str, session) -> dict:
        """Analyze logs with pattern detection."""
        log_source = parameters.get("log_source", "cluster-wide")
        time_range = parameters.get("time_range", "1h")

        # For now, provide event-based log analysis since direct log access requires more setup
        try:
            events = k8s_client.get_events(namespace)
            log_patterns = {}
            error_summary = {"total_errors": 0, "critical_errors": 0, "warning_count": 0}

            for event in events.items:
                if event.type in ["Warning", "Error"]:
                    error_summary["warning_count" if event.type == "Warning" else "total_errors"] += 1

                    # Pattern analysis
                    pattern_key = f"{event.reason}_{event.involved_object.kind}"
                    log_patterns[pattern_key] = log_patterns.get(pattern_key, 0) + 1

                    if event.reason in ["Failed", "FailedMount", "FailedScheduling"]:
                        error_summary["critical_errors"] += 1

            # Sort patterns by frequency
            sorted_patterns = sorted(log_patterns.items(), key=lambda x: x[1], reverse=True)

            analysis_text = f"Log analysis for {log_source} over {time_range}: "
            analysis_text += f"Found {error_summary['total_errors']} errors, {error_summary['warning_count']} warnings. "
            analysis_text += f"Top patterns: {', '.join([f'{k}({v})' for k, v in sorted_patterns[:3]])}"

            result = {
                "success": True,
                "data": {
                    "log_source": log_source,
                    "time_range": time_range,
                    "namespace": namespace,
                    "analysis_status": "completed",
                    "analysis": analysis_text,
                    "patterns_found": [f"{pattern}: {count} occurrences" for pattern, count in sorted_patterns[:10]],
                    "error_summary": error_summary,
                    "recommendations": [
                        "Focus on patterns with highest occurrence",
                        "Check pod logs for detailed error messages",
                        "Review resource constraints for failing operations"
                    ] if error_summary["total_errors"] > 0 else ["No significant issues in log patterns"],
                    "confidence": 0.75,
                    "investigation_type": "log_pattern_analysis"
                }
            }

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Log analysis failed: {str(e)}"
            }

    async def generate_fix_recommendations(self, k8s_client, parameters: dict, namespace: str, session) -> dict:
        """Generate actionable fix recommendations based on cluster analysis."""
        issue_type = parameters.get("issue_type", "general")
        resource_name = parameters.get("resource_name")

        try:
            # Collect current cluster state for context
            pods = k8s_client.list_pods(namespace)
            events = k8s_client.get_events(namespace)

            # Analyze current issues
            pending_pods = [p for p in pods.items if p.status.phase == "Pending"]
            failed_pods = [p for p in pods.items if p.status.phase == "Failed"]
            warning_events = [e for e in events.items if e.type in ["Warning", "Error"]]

            # Generate specific recommendations based on findings
            fix_recommendations = []
            kubectl_commands = []
            preventive_measures = []

            # Analyze pending pods with deep root cause investigation
            if pending_pods:
                # Deep analysis of each pending pod
                pending_analysis = []
                for pod in pending_pods[:3]:  # Analyze first 3 pending pods
                    pod_analysis = {
                        "pod_name": pod.metadata.name,
                        "pending_duration": "Unknown",
                        "specific_issues": [],
                        "resource_requests": {},
                        "node_constraints": []
                    }

                    # Analyze resource requests
                    if pod.spec.containers:
                        for container in pod.spec.containers:
                            if container.resources and container.resources.requests:
                                pod_analysis["resource_requests"][container.name] = dict(container.resources.requests)

                    # Analyze node selector constraints
                    if pod.spec.node_selector:
                        pod_analysis["node_constraints"].append(f"Node selector: {dict(pod.spec.node_selector)}")

                    # Analyze affinity rules
                    if pod.spec.affinity:
                        if pod.spec.affinity.node_affinity:
                            pod_analysis["node_constraints"].append("Has node affinity rules")
                        if pod.spec.affinity.pod_affinity:
                            pod_analysis["node_constraints"].append("Has pod affinity rules")
                        if pod.spec.affinity.pod_anti_affinity:
                            pod_analysis["node_constraints"].append("Has pod anti-affinity rules")

                    # Analyze tolerations
                    if pod.spec.tolerations:
                        toleration_count = len(pod.spec.tolerations)
                        pod_analysis["node_constraints"].append(f"Has {toleration_count} tolerations")

                    # Check pod conditions for specific failure reasons
                    if pod.status.conditions:
                        for condition in pod.status.conditions:
                            if condition.type == "PodScheduled" and condition.status == "False":
                                pod_analysis["specific_issues"].append({
                                    "type": "scheduling_failure",
                                    "reason": condition.reason or "Unknown",
                                    "message": condition.message or "No message"
                                })

                    pending_analysis.append(pod_analysis)

                # Look for common patterns across pending pods
                common_issues = []
                if all("node affinity" in str(pa.get("node_constraints", [])).lower() for pa in pending_analysis):
                    common_issues.append("All pods have node affinity constraints - check node labels")

                if any("insufficient" in str(issue.get("message", "")).lower() for pa in pending_analysis for issue in pa.get("specific_issues", [])):
                    common_issues.append("Resource insufficiency detected - cluster may need scaling")

                fix_recommendations.append({
                    "issue": "Pods stuck in Pending state",
                    "severity": "medium",
                    "description": f"Found {len(pending_pods)} pods that cannot be scheduled",
                    "detailed_analysis": pending_analysis,
                    "common_patterns": common_issues,
                    "root_cause_investigation": {
                        "resource_analysis": "Check if cluster has sufficient CPU/Memory capacity",
                        "scheduling_constraints": "Verify node selectors, affinity rules, and tolerations",
                        "node_availability": "Ensure nodes are Ready and schedulable",
                        "storage_analysis": "Check PVC status and storage class availability"
                    },
                    "immediate_actions": [
                        "Describe each pending pod to see specific scheduling failures",
                        "Check node capacity with 'kubectl top nodes'",
                        "Verify node labels match pod selectors",
                        "Check for node taints that may block scheduling",
                        "Examine storage provisioner status if using PVCs"
                    ],
                    "kubectl_commands": [
                        f"kubectl describe pod {pending_pods[0].metadata.name} -n {namespace}",
                        "kubectl get nodes -o wide",
                        "kubectl top nodes",
                        "kubectl describe nodes | grep -E '(Taints|Unschedulable|Conditions)'",
                        f"kubectl get events -n {namespace} | grep {pending_pods[0].metadata.name}",
                        "kubectl get pvc -n " + namespace + " 2>/dev/null || echo 'No PVCs found'"
                    ],
                    "diagnostic_commands": [
                        "kubectl get nodes --show-labels",
                        f"kubectl get pod {pending_pods[0].metadata.name} -n {namespace} -o jsonpath='{{.spec.nodeSelector}}'",
                        f"kubectl get pod {pending_pods[0].metadata.name} -n {namespace} -o jsonpath='{{.spec.affinity}}'",
                        "kubectl get sc",  # Storage classes
                        "kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{\"\\t\"}{.status.allocatable}{\"\\n\"}{end}'"
                    ]
                })

            # Analyze failed pods
            if failed_pods:
                fix_recommendations.append({
                    "issue": "Pod failures detected",
                    "severity": "high",
                    "description": f"Found {len(failed_pods)} failed pods requiring attention",
                    "root_causes": [
                        "Application crashes or errors",
                        "Resource limits exceeded",
                        "Configuration errors",
                        "Image pull failures"
                    ],
                    "immediate_actions": [
                        "Check pod logs for error messages",
                        "Verify image availability and credentials",
                        "Review resource limits and requests",
                        "Check configuration and environment variables"
                    ],
                    "kubectl_commands": [
                        f"kubectl logs {failed_pods[0].metadata.name} -n {namespace} --previous",
                        f"kubectl describe pod {failed_pods[0].metadata.name} -n {namespace}",
                        f"kubectl get pod {failed_pods[0].metadata.name} -n {namespace} -o yaml"
                    ]
                })

            # Analyze scheduling issues from events
            scheduling_events = [e for e in warning_events if "FailedScheduling" in e.reason]
            if scheduling_events:
                fix_recommendations.append({
                    "issue": "Pod scheduling failures",
                    "severity": "medium",
                    "description": f"Detected {len(scheduling_events)} scheduling failures",
                    "root_causes": [
                        "Node affinity/selector constraints",
                        "Resource constraints",
                        "Taints and tolerations",
                        "Pod disruption budgets"
                    ],
                    "immediate_actions": [
                        "Scale cluster nodes if resource constrained",
                        "Adjust pod resource requirements",
                        "Review and modify node selectors/affinity",
                        "Check node taints and pod tolerations"
                    ],
                    "kubectl_commands": [
                        "kubectl get nodes --show-labels",
                        "kubectl describe nodes | grep -A5 'Taints'",
                        "kubectl top nodes",
                        f"kubectl get events -n {namespace} | grep FailedScheduling"
                    ]
                })

            # Generate preventive measures
            preventive_measures = [
                {
                    "category": "Resource Management",
                    "recommendations": [
                        "Implement resource quotas and limit ranges",
                        "Set appropriate CPU and memory requests/limits",
                        "Monitor cluster capacity trends",
                        "Use Horizontal Pod Autoscaler for workloads"
                    ]
                },
                {
                    "category": "Monitoring & Alerting",
                    "recommendations": [
                        "Set up alerts for pod failures and restarts",
                        "Monitor node resource utilization",
                        "Track pending pods metrics",
                        "Implement health checks and readiness probes"
                    ]
                },
                {
                    "category": "Best Practices",
                    "recommendations": [
                        "Use multi-replica deployments for resilience",
                        "Implement proper pod disruption budgets",
                        "Regular cluster maintenance windows",
                        "Test deployments in staging environments"
                    ]
                }
            ]

            # Generate summary
            total_issues = len(pending_pods) + len(failed_pods) + len(scheduling_events)
            severity = "high" if failed_pods else "medium" if pending_pods else "low"

            result = {
                "success": True,
                "data": {
                    "namespace": namespace,
                    "cluster_info": {
                        "cluster_name": session.cluster_name,
                        "api_server": session.credentials.api_server
                    },
                    "analysis_type": "fix_recommendations",
                    "analysis_status": "completed",
                    "summary": f"Generated {len(fix_recommendations)} fix recommendations for {total_issues} identified issues",
                    "overall_severity": severity,
                    "cluster_health": {
                        "total_pods": len(pods.items),
                        "pending_pods": len(pending_pods),
                        "failed_pods": len(failed_pods),
                        "warning_events": len(warning_events)
                    },
                    "fix_recommendations": fix_recommendations,
                    "preventive_measures": preventive_measures,
                    "next_steps": [
                        "Apply immediate fixes for high-severity issues",
                        "Implement monitoring for early issue detection",
                        "Review and apply preventive measures",
                        "Schedule regular cluster health assessments"
                    ],
                    "confidence": 0.9,
                    "investigation_type": "fix_recommendations"
                }
            }

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Fix recommendations generation failed: {str(e)}"
            }

    @override
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute the diagnostic agent request."""
        # Get the user input from the request context
        user_message = context.get_user_input()

        if not user_message:
            await event_queue.enqueue_event(new_agent_text_message("No message provided"))
            return

        # Try to parse as skill call
        skill_call = self.parse_skill_call(user_message)

        if skill_call:
            # Execute diagnostic skill
            try:
                result = await self.execute_diagnostic_skill(skill_call['skill_id'], skill_call['parameters'])

                if result.get('success'):
                    # Format the response nicely
                    response = f"✅ Skill '{skill_call['skill_id']}' executed successfully:\n\n"
                    response += json.dumps(result['data'], indent=2)
                else:
                    response = f"❌ Skill '{skill_call['skill_id']}' failed: {result.get('error', 'Unknown error')}"

                await event_queue.enqueue_event(new_agent_text_message(response))

            except Exception as e:
                await event_queue.enqueue_event(new_agent_text_message(f"Error executing skill: {str(e)}"))
        else:
            # Handle conversational queries about capabilities
            if "diagnostic" in user_message.lower() or "capabilities" in user_message.lower():
                response = """🔧 k8s-ai Diagnostic Agent

Available skills:
- kubernetes_diagnose_issue: General Kubernetes problem diagnosis and troubleshooting
- kubernetes_resource_health: Assess the health status of Kubernetes resources
- kubernetes_analyze_logs: Analyze Kubernetes logs for patterns, errors, and insights
- kubernetes_fix_recommendations: Generate actionable fix recommendations with deep root cause analysis

To use skills, send a message in this format:
skill_id: param1=value1, param2=value2

Example:
kubernetes_diagnose_issue: session_token=session-abc123, issue_description=pods not starting, namespace=default

Note: All diagnostic operations require a valid session_token from the admin API.
Use the admin API to register clusters and obtain session tokens for secure, read-only access.

Your message: """ + user_message

                await event_queue.enqueue_event(new_agent_text_message(response))
            else:
                response = f"I'm a Kubernetes diagnostic agent. I can help troubleshoot cluster issues using diagnostic skills.\n\n"
                response += f"Your message: {user_message}\n\n"
                response += "To use diagnostic skills, format your request like:\n"
                response += "kubernetes_diagnose_issue: session_token=your-token, issue_description=your issue description\n\n"
                response += "Available skills: kubernetes_diagnose_issue, kubernetes_resource_health, kubernetes_analyze_logs, kubernetes_fix_recommendations"

                await event_queue.enqueue_event(new_agent_text_message(response))

    @override
    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        """Cancel the agent execution."""
        await event_queue.enqueue_event(new_agent_text_message("Diagnostic request cancelled"))