"""Agents for Zoho automation."""
from .base_agent import BaseAgent
from .desk_agent import DeskTicketAgent
from .crm_agent import CRMOpportunityAgent
from .crm_update_agent import CRMUpdateAgent
from .deal_linking_agent import DealLinkingAgent
from .dispatcher_agent import TicketDispatcherAgent
from .examt3p_agent import ExamT3PAgent

__all__ = [
    "BaseAgent",
    "DeskTicketAgent",
    "CRMOpportunityAgent",
    "CRMUpdateAgent",
    "DealLinkingAgent",
    "TicketDispatcherAgent",
    "ExamT3PAgent"
]
