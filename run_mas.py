#!/usr/bin/env python

import argparse
import asyncio
import sys
import mapc_env
import agentspeak.runtime
import logging



def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        "--agents",
        type=int,
        default=10,
        help="number of agents to start (1-10)",
    )
    parser.add_argument("--host", default="localhost", help="MASSim server host")
    parser.add_argument("--port", type=int, default=12300, help="MASSim server port")
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=30.0,
        help="seconds to keep retrying while waiting for MASSim",
    )
    return parser.parse_args()


async def connect_with_retry(agent, host, port, timeout):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    last_error = None

    while loop.time() <= deadline:
        try:
            return await agent.connect(agent.name, "a", host=host, port=port)
        except OSError as exc:
            last_error = exc
            await asyncio.sleep(1)

    raise ConnectionError(
        f"Could not connect to MASSim at {host}:{port} after {timeout:.0f}s. "
        "Start the server first with: java -jar massim.jar"
    ) from last_error


async def main(agent_count, host, port, connect_timeout):
    env = mapc_env.Environment()

    agents = []
    agent_count = max(1, min(10, agent_count))
    names = [f"agentA{i}" for i in range(1, agent_count + 1)]
    for name in names:
        with open("agent.asl") as source:
            agents.append(
                env.build_agent(source, mapc_env.actions, mapc_env.Agent, name)
            )

    for agent in agents:
        await connect_with_retry(agent, host, port, connect_timeout)


if __name__ == "__main__":
    args = parse_args()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            main(args.agents, args.host, args.port, args.connect_timeout)
        )
        loop.run_forever()
    except ConnectionError as exc:
        print(exc, file=sys.stderr)
        print(
            "Open another PowerShell in this folder, run `java -jar massim.jar`, "
            "choose config `0`, then press ENTER to start the tournament.",
            file=sys.stderr,
        )
        sys.exit(1)
    finally:
        loop.close()
