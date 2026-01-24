"""Agents for Zoho automation."""
from .base_agent import BaseAgent
from .desk_agent import DeskTicketAgent
from .crm_agent import CRMOpportunityAgent
from .deal_linking_agent import DealLinkingAgent

__all__ = ["BaseAgent", "DeskTicketAgent", "CRMOpportunityAgent", "DealLinkingAgent"]
