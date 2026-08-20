# Multi-Agent Coordination System

A **multi-agent autonomous coordination system** developed for an MAPC-like scenario using **Python, AgentSpeak, and MASSim**.

The project demonstrates autonomous decision-making, cooperative task execution, pathfinding, resource management, and communication between multiple software agents operating in a shared hexagonal environment.

## Overview

The system controls a team of up to **10 autonomous agents** operating simultaneously in the MASSim simulation environment.

Agents start at the origin and independently explore the environment while sharing useful knowledge with the team. They must:

* explore unknown areas,
* avoid blocked terrain,
* locate and collect data,
* manage limited energy,
* navigate toward recharge locations,
* transmit collected data to the origin,
* and cooperate with other agents when direct transmission is inefficient.

The implementation follows a **hybrid architecture**:

* **AgentSpeak** handles high-level symbolic decision-making and agent behavior.
* **Python** provides runtime support and computation-heavy functionality such as pathfinding, communication, state management, exploration heuristics, and relay coordination.

---

## Key Features

### Multi-Agent Execution

The runtime can start between **1 and 10 agents** in parallel and connect them to the MASSim simulation server.

All agents use the same AgentSpeak behavior model while making independent decisions based on their:

* position,
* current percepts,
* energy,
* stored knowledge,
* assigned tasks,
* and communication with other agents.

### Autonomous Exploration

Agents explore the hexagonal environment using structured exploration rather than purely random movement.

The exploration strategy considers:

* previously visited cells,
* team-wide visit frequency,
* individual agent direction biases,
* known obstacles,
* and exploration boundaries.

This reduces unnecessary overlap between agents and improves map coverage.

### A* Pathfinding

The Python runtime implements **A*-style pathfinding** for navigation.

Pathfinding is used when agents need to move toward:

* discovered data,
* recharge locations,
* the origin,
* or assigned relay positions.

If A* cannot find a valid route, the system uses bounded greedy movement as a fallback to reduce the chance of an agent becoming stuck.

### Obstacle-Aware Navigation

The environment contains blocked cells represented as mountains.

Agents maintain knowledge about discovered obstacles and avoid them during both path planning and local movement decisions.

Obstacle information can also contribute to shared team knowledge.

### Energy Management

Agents operate with limited energy.

When an agent's energy becomes low, its behavior changes toward finding a known **oasis** where it can recharge.

The system includes:

* oasis discovery,
* path planning toward recharge locations,
* fallback movement,
* and recharge behavior.

### Data Claiming

To prevent multiple agents from unnecessarily pursuing the same data item, the runtime implements a temporary **data-claiming mechanism**.

Agents can claim discovered data positions for a limited period, reducing duplicated work and improving coordination.

### Contract Net Protocol Inspired Coordination

For data that cannot be efficiently transmitted directly to the origin, the system uses a **Contract Net Protocol (CNP)-inspired coordination mechanism**.

A data-carrying agent can act as a manager and announce a relay task.

Other agents can evaluate the request and submit bids based on factors such as:

* their position,
* distance to the origin,
* available energy,
* and current commitments.

The manager evaluates the available agents and prepares a cooperative transmission route.

### Relay-Based Data Transmission

The system supports cooperative transmission using relay agents.

Two coordination strategies are supported:

**Immediate relay**

If suitable agents are already positioned correctly, the system can schedule the transmission directly.

**Mobilized relay**

If relay agents are not yet in appropriate positions, the system assigns movement tasks first and schedules the data transfer for a later simulation step.

This allows multiple agents to cooperate on a single transmission task.

---

## System Architecture

```text
                  MASSim Simulation Server
                           │
                           │ JSON / Socket Communication
                           ▼
                  Python Runtime Layer
                    mapc_env.py
                           │
          ┌────────────────┼────────────────┐
          │                │                │
      Pathfinding      Shared State     Communication
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                  AgentSpeak Reasoning
                      agent.asl
                           │
                           ▼
               Autonomous Agent Actions
                           
          Explore │ Move │ Recharge │ Send │ Relay
```

The separation between symbolic reasoning and algorithmic computation keeps the system modular.

AgentSpeak decides **what an agent should do**, while Python provides the functionality required to execute those decisions effectively.

---

## Environment

The simulation uses a **hexagonal grid** represented using cube coordinates:

```text
(q, r, s)
```

Agent movement is possible in six directions.

Distance between two cells is calculated using the standard hex-grid distance:

```text
d(a, b) = max(|q1 - q2|, |r1 - r2|, |s1 - s2|)
```

The origin is represented as:

```text
(0, 0, 0)
```

This distance metric is used for:

* pathfinding,
* selecting data targets,
* determining transmission range,
* evaluating relay candidates,
* and navigation toward the origin.

---

## Decision Flow

During each simulation step:

```text
Receive percepts from MASSim
          │
          ▼
Update agent beliefs and shared state
          │
          ▼
Synchronize agent simulation state
          │
          ▼
AgentSpeak evaluates applicable plans
          │
          ▼
Python support functions calculate required actions
          │
          ▼
Agent executes Move / Send / Relay / Recharge / Skip
```

The runtime processes percepts before allowing the next decision cycle, ensuring that agents make decisions using a consistent internal state.

---

## Main Agent Behaviors

The AgentSpeak layer includes plans for:

* exploration,
* recovering from out-of-zone positions,
* moving toward discovered data,
* low-energy recovery,
* recharging,
* direct data transmission,
* bidding for relay tasks,
* managing contract-net tasks,
* scheduled sending,
* scheduled relaying,
* relay positioning,
* and local patrol near the origin.

---

## Technologies

**Languages**

* Python
* AgentSpeak

**Concepts & Techniques**

* Multi-Agent Systems
* Autonomous Agents
* Symbolic AI
* Agent-Oriented Programming
* A* Search
* Path Planning
* Distributed Coordination
* Contract Net Protocol
* Task Allocation
* Cooperative Agents
* State Management
* Asynchronous Programming
* Socket Communication

**Platform**

* MASSim

---

## Repository Structure

```text
multi-agent-coordination-system/
│
├── agent.asl
│   └── High-level AgentSpeak plans and decision logic
│
├── mapc_env.py
│   └── Python runtime, pathfinding, environment handling,
│       coordination and MASSim communication
│
├── run_mas.py
│   └── Multi-agent startup and server connection
│
├── .gitignore
│
└── README.md
```

---

## Running the System

The project requires a compatible **MASSim server** and the Python/AgentSpeak environment used by the project.

Start the MASSim server first:

```bash
java -jar massim.jar
```

Then start the multi-agent system:

```bash
python run_mas.py
```

The number of agents can also be configured:

```bash
python run_mas.py --agents 10
```

Additional runtime parameters include:

```text
--host
--port
--connect-timeout
```

For example:

```bash
python run_mas.py --agents 10 --host localhost --port 12300
```

---

## Example Behaviors

During a simulation, agents dynamically switch between behaviors such as:

```text
Exploring
Moving toward data
Low energy — heading to oasis
Recharging
Preparing relay task
Moving to relay position
Sending data
Relaying data
```

The system was successfully executed with **10 agents operating concurrently** in the MASSim environment.

Runtime testing demonstrated autonomous exploration, inter-agent communication, energy-aware behavior, data pursuit, and cooperative execution.

---

## Project Context

This project was developed as part of an **Agent-Oriented Programming** university project.

The objective was to design and implement a functional multi-agent system capable of autonomous operation and cooperation in an MAPC-like simulation environment.

The final implementation goes beyond independent agent movement by combining:

* autonomous decision-making,
* persistent environmental knowledge,
* path planning,
* resource-aware behavior,
* inter-agent communication,
* distributed task allocation,
* and coordinated execution.

## Authors

**Ramin Pourheidar Shirazi**

---

## What I Learned

This project provided practical experience with designing systems in which multiple autonomous components must make local decisions while contributing to a shared objective.

Key areas of experience included:

* designing autonomous agent behavior,
* separating high-level reasoning from low-level algorithms,
* implementing A* search and fallback navigation,
* managing shared and per-agent state,
* coordinating asynchronous agents,
* designing cooperative task allocation,
* handling communication between autonomous agents,
* and debugging distributed behavior in a simulation environment.

