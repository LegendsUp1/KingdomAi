#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MASS Framework Module for Kingdom AI

Multi-Agent System Search (MASS) Framework implementation for Kingdom AI.
Provides agent-based components that can collaborate in various topologies
to solve complex tasks through agent communication and orchestration.

Classes:
    MASSAgent: Base agent class for MASS framework
    MASSTopology: Base topology interface
    DebateTopology: Concrete debate-oriented topology
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# Get module logger
logger = logging.getLogger(__name__)


class MASSAgent:
    """Base agent class for MASS (Multi-Agent System Search) framework."""
    
    def __init__(self, name: str, role: str, event_bus=None) -> None:
        """Initialize a MASS Agent.
        
        Args:
            name: Unique identifier for this agent
            role: The agent's role in the system (e.g., researcher, critic)
            event_bus: Event bus for agent communication
        """
        self.name = name
        self.role = role
        self.event_bus = event_bus
        self.message_queue = asyncio.Queue()
        self.knowledge_base = {}
        self.initialized = False
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
    
    async def initialize(self) -> bool:
        """Initialize the agent and connect to the event bus."""
        self.logger.info(f"Initializing agent {self.name} with role {self.role}")
        
        if self.event_bus:
            # Register event handlers for agent-specific events
            await self.event_bus.subscribe(f"mass.agent.{self.name}.message", self._handle_message)
            await self.event_bus.subscribe("mass.broadcast", self._handle_broadcast)
            
        self.initialized = True
        self.logger.info(f"Agent {self.name} initialized successfully")
        return True
    
    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Process a message directed to this agent.
        
        Args:
            data: Message data
        """
        self.logger.debug(f"Agent {self.name} received message: {data}")
        await self.message_queue.put(data)
        
    async def _handle_broadcast(self, data: Dict[str, Any]) -> None:
        """Process a broadcast message.
        
        Args:
            data: Broadcast message data
        """
        self.logger.debug(f"Agent {self.name} received broadcast: {data}")
        await self.message_queue.put(data)
    
    async def send_message(self, target_agent: str, content: Dict[str, Any]) -> None:
        """Send a message to another agent.
        
        Args:
            target_agent: Name of the recipient agent
            content: Message content
        """
        if not self.initialized or not self.event_bus:
            self.logger.error(f"Agent {self.name} cannot send messages before initialization")
            return
            
        message = {
            "source": self.name,
            "target": target_agent,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.event_bus.publish(f"mass.agent.{target_agent}.message", message)
        self.logger.debug(f"Agent {self.name} sent message to {target_agent}")
    
    async def broadcast_message(self, content: Dict[str, Any]) -> None:
        """Broadcast a message to all agents.
        
        Args:
            content: Message content
        """
        if not self.initialized or not self.event_bus:
            self.logger.error(f"Agent {self.name} cannot broadcast before initialization")
            return
            
        message = {
            "source": self.name,
            "broadcast": True,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.event_bus.publish("mass.broadcast", message)
        self.logger.debug(f"Agent {self.name} broadcasted message to all agents")
    
    async def process_message(self) -> Optional[Dict[str, Any]]:
        """Process the next message in the queue.
        
        Returns:
            The processed message or None if queue is empty
        """
        if self.message_queue.empty():
            return None
            
        message = await self.message_queue.get()
        self.logger.debug(f"Agent {self.name} processing message: {message}")
        
        # Default implementation just returns the message
        # Subclasses should override this to provide specific processing
        return message
    
    async def update_knowledge(self, key: str, value: Any) -> None:
        """Update agent's knowledge base.
        
        Args:
            key: Knowledge identifier
            value: Knowledge content
        """
        self.knowledge_base[key] = value
        self.logger.debug(f"Agent {self.name} knowledge updated: {key}")


class MASSTopology:
    """Base class for MASS agent topologies."""
    
    def __init__(self, event_bus=None) -> None:
        """Initialize a MASS Topology.
        
        Args:
            event_bus: Event bus for communication
        """
        self.event_bus = event_bus
        self.agents = {}
        self.initialized = False
        self.logger = logging.getLogger(f"{__name__}.MASSTopology")
    
    async def initialize(self) -> bool:
        """Initialize the topology."""
        self.logger.info("Initializing MASS topology")
        self.initialized = True
        return True
    
    async def register_agent(self, agent: MASSAgent) -> bool:
        """Register an agent with this topology.
        
        Args:
            agent: Agent to register
            
        Returns:
            Success status
        """
        if not self.initialized:
            self.logger.error("Cannot register agent with uninitialized topology")
            return False
            
        if agent.name in self.agents:
            self.logger.warning(f"Agent {agent.name} already registered with this topology")
            return False
            
        self.agents[agent.name] = agent
        self.logger.info(f"Agent {agent.name} registered with topology")
        return True
    
    async def unregister_agent(self, agent_name: str) -> bool:
        """Unregister an agent from this topology.
        
        Args:
            agent_name: Name of agent to unregister
            
        Returns:
            Success status
        """
        if agent_name not in self.agents:
            self.logger.warning(f"Agent {agent_name} not registered with this topology")
            return False
            
        del self.agents[agent_name]
        self.logger.info(f"Agent {agent_name} unregistered from topology")
        return True
    
    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all registered agents.
        
        Args:
            message: Message to broadcast
        """
        if not self.initialized:
            self.logger.error("Cannot broadcast message with uninitialized topology")
            return
            
        for agent_name, agent in self.agents.items():
            try:
                await agent._handle_message(message)
            except Exception as e:
                self.logger.error(f"Error sending broadcast to {agent_name}: {e}")
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task using the agents in this topology.
        
        Args:
            task_data: Task data
            
        Returns:
            Task result
        """
        self.logger.info(f"Processing task: {task_data.get('type', 'unknown')}")
        # Base implementation just logs the task
        # Concrete topologies must implement actual processing
        return {"status": "base_class", "message": "Subclass this topology and override process_task()"}


class DebateTopology(MASSTopology):
    """Debate-oriented agent topology where agents discuss and critique solutions."""
    
    async def initialize(self) -> bool:
        """Initialize the debate topology."""
        self.logger.info("Initializing Debate Topology")
        self.roles = {
            "researcher": [],
            "critic": [],
            "synthesizer": []
        }
        return await super().initialize()
    
    async def register_agent(self, agent: MASSAgent) -> bool:
        """Register an agent with this topology and catalog its role.
        
        Args:
            agent: Agent to register
            
        Returns:
            Success status
        """
        result = await super().register_agent(agent)
        if result and agent.role in self.roles:
            self.roles[agent.role].append(agent.name)
        return result
    
    async def unregister_agent(self, agent_name: str) -> bool:
        """Unregister an agent from this topology.
        
        Args:
            agent_name: Name of agent to unregister
            
        Returns:
            Success status
        """
        if agent_name in self.agents:
            agent = self.agents[agent_name]
            if agent.role in self.roles and agent_name in self.roles[agent.role]:
                self.roles[agent.role].remove(agent_name)
                
        return await super().unregister_agent(agent_name)
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task using debate protocol.
        
        Args:
            task_data: Task data
            
        Returns:
            Task result
        """
        self.logger.info(f"Processing task with debate protocol: {task_data.get('type', 'unknown')}")
        
        # Step 1: Assign task to researcher agents
        researcher_results = await self._research_phase(task_data)
        
        # Step 2: Critic agents evaluate researcher findings
        critic_results = await self._critique_phase(researcher_results)
        
        # Step 3: Synthesizer agents create final output
        final_result = await self._synthesis_phase(researcher_results, critic_results)
        
        return {
            "status": "success",
            "result": final_result,
            "researcher_contributions": researcher_results,
            "critic_evaluations": critic_results
        }
    
    async def _research_phase(self, task_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the research phase of the debate.
        
        Args:
            task_data: Original task data
            
        Returns:
            List of research results
        """
        results = []
        researcher_count = len(self.roles.get("researcher", []))
        
        if researcher_count == 0:
            self.logger.warning("No researcher agents available for research phase")
            return results
            
        # For each researcher agent, send the task and collect results
        for agent_name in self.roles.get("researcher", []):
            if agent_name in self.agents:
                agent = self.agents[agent_name]
                
                # Send task to researcher
                research_task = {
                    "phase": "research",
                    "task": task_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                await agent._handle_message(research_task)
                
                # In a real implementation, we would await for a response
                # For testing, we'll simulate an immediate response
                result = {
                    "agent": agent_name,
                    "findings": f"Research findings from {agent_name} for task {task_data.get('type', 'unknown')}",
                    "confidence": 0.8
                }
                results.append(result)
                
        return results
    
    async def _critique_phase(self, research_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute the critique phase of the debate.
        
        Args:
            research_results: Results from research phase
            
        Returns:
            List of critiques
        """
        critiques = []
        critic_count = len(self.roles.get("critic", []))
        
        if critic_count == 0:
            self.logger.warning("No critic agents available for critique phase")
            return critiques
            
        # For each critic agent, send research results and collect critiques
        for agent_name in self.roles.get("critic", []):
            if agent_name in self.agents:
                agent = self.agents[agent_name]
                
                # Send research results to critic
                critique_task = {
                    "phase": "critique",
                    "research_results": research_results,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                await agent._handle_message(critique_task)
                
                # In a real implementation, we would await for a response
                # For testing, we'll simulate an immediate response
                critique = {
                    "agent": agent_name,
                    "critiques": [{"target": r["agent"], "analysis": f"Critique of {r['agent']}'s findings"} 
                                  for r in research_results],
                    "overall_assessment": "Research generally sound with minor issues"
                }
                critiques.append(critique)
                
        return critiques
    
    async def _synthesis_phase(self, 
                              research_results: List[Dict[str, Any]], 
                              critic_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute the synthesis phase of the debate.
        
        Args:
            research_results: Results from research phase
            critic_results: Results from critique phase
            
        Returns:
            Synthesized result
        """
        synthesizer_count = len(self.roles.get("synthesizer", []))
        
        if synthesizer_count == 0:
            self.logger.warning("No synthesizer agents available for synthesis phase")
            # Return a basic synthesis if no synthesizer agents
            return {
                "summary": "Auto-generated synthesis due to lack of synthesizer agents",
                "recommendations": ["No specific recommendations available"],
                "confidence": 0.5
            }
            
        # Use the first synthesizer for now (in real implementation, might use voting or consensus)
        synthesizer_name = self.roles["synthesizer"][0]
        if synthesizer_name in self.agents:
            agent = self.agents[synthesizer_name]
                
            # Send all data to synthesizer
            synthesis_task = {
                "phase": "synthesis",
                "research_results": research_results,
                "critic_results": critic_results,
                "timestamp": datetime.utcnow().isoformat()
            }
                
            await agent._handle_message(synthesis_task)
                
            # In a real implementation, we would await for a response
            # For testing, we'll simulate an immediate response
            return {
                "summary": f"Synthesis by {synthesizer_name}",
                "key_findings": ["Finding 1", "Finding 2"],
                "recommendations": ["Recommendation 1", "Recommendation 2"],
                "confidence": 0.9
            }
        
        return {
            "summary": "Failed to process synthesis phase",
            "error": "Synthesizer agent unavailable",
            "confidence": 0.0
        }
