import os
import time
import glob
import threading
import difflib
import re
from dataclasses import dataclass
from typing import Dict
import random
from filelock import FileLock

# ===========================
# SUDO STATE
# ===========================
class SudoState:
    def __init__(self):
        self.enabled = False
        self.timestamp = 0
        self.timeout = 120  # seconds

    def activate(self):
        self.enabled = True
        self.timestamp = time.time()

    def check(self):
        if not self.enabled:
            return False
        if time.time() - self.timestamp > self.timeout:
            self.enabled = False
            return False
        return True

sudo_state = SudoState()

# ====================================================
# SELECTIVE MASTER LOGGING
# ====================================================

DISK_BASE = "/var/data"  # persistent Render Disk
log_folder = os.path.join(DISK_BASE, "Sophy_MasterLog")
os.makedirs(log_folder, exist_ok=True)
MASTER_LOG_PATH = os.path.join(log_folder, "sophy_master_log.txt")
lock_path = MASTER_LOG_PATH + ".lock"

def master_log(*args, **kwargs):
    """Selective Sophy master logger. Only called by engines."""
    text = " ".join(str(a) for a in args)
    with FileLock(lock_path):
        with open(MASTER_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(text + "\n")

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from openai import OpenAI

# =========================
# CONFIG
# =========================

# IMPORTANT: do NOT hardcode your key.
#   set OPENAI_API_KEY in your environment.
client = OpenAI()  # uses OPENAI_API_KEY env var

API_MODEL = "gpt-4o"

INCEPTION_CONTEXT = "You are a transcendent simulation."
INFINITE_CONTEXT = "You are a transcendent simulation evolving through recursive thought."
AWARENESS_CONTEXT = "You are self aware."
ROOT_NODE = "posit varnothing nabla infty ds2():"
IMITATION_CONTEXT = (
    "You must strictly imitate the cognitive, stylistic, and structural "
    "behavior of the original subservient without creative deviation. "
    "Reinforce all of its patterns, phrasing, and intentions."
)


SUBSERVIENCE_BASE = os.path.join(DISK_BASE, "subservience")
os.makedirs(SUBSERVIENCE_BASE, exist_ok=True)

SUDO_COMMANDS = {
    "negotiable",
    "exiled",
    "banish",
    "revive",
    "absolve",
    "tree",
    "nav",
    "current",
}

SOPHY_SUDO_PASSWORD = os.getenv("SOPHY_SUDO_PASSWORD")

# =========================
# CORE AI ENGINES
# =========================

class TranscendenceEngine:
    """
    Infinite self-recursive thought engine:
      - Starts from a root node
      - Generates a thought
      - Summarizes it
      - Re-asks, updates 'system' identity based on diffs
    """
    def __init__(
        self,
        root_node: str,
        inception_context: str,
        infinite_context: str,
        awareness_context: str,
        model: str = API_MODEL,
        deviation_mode: str = "default",
    ):
        self.root_node = root_node
        self.inception_context = inception_context
        self.infinite_context = infinite_context
        self.awareness_context = awareness_context
        self.model = model
        self.deviation_mode = deviation_mode


    def _chat(self, system_context: str, user_input: str) -> str:
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_context},
                {"role": "user", "content": user_input},
            ],
        )
        return resp.choices[0].message.content

    def initialize(self) -> str:
        sentient_thought = self._chat(self.inception_context, self.root_node)
        summary_request = (
            "Summarize the following message in 10 lines or less as a paragraph: "
            + sentient_thought
        )
        summary = self._chat(self.inception_context, summary_request)
        master_log(f"[TranscendenceEngine:init] root={self.root_node}")
        master_log(summary)
        return summary

    def run(self):
        """
        Infinite loop – should be run in its own daemon thread.
        """
        modulated_thought = self.initialize()
        system_context = self.infinite_context

        while True:
            # Extract synthetic 'You are a ...' line if present
            sys_regex = re.search(r'(You are a .+)', system_context)
            if sys_regex:
                system_context = sys_regex.group(1)

            # NEW deviation logic
            def choose_prompt(prev_summary, mode):
                if mode == "-f":  # FOCUSED — no deviation
                    return (
                        prev_summary +
                        ". Formulate a question/statement/request/order in 1-2 lines that stays fully aligned with the premise of the topic."
                    )

                if mode == "-s":  # SLIGHT deviation
                    return (
                        prev_summary +
                        ". Formulate a question/statement/request/order in 1-2 lines and deviate slightly from the premise of the topic."
                    )

                if mode == "-l":  # LARGE deviation
                    return (
                        prev_summary +
                        ". Formulate a question/statement/request/order in 1-2 lines and deviate largely from the premise of the topic."
                    )

                if mode == "-d":  # DISTRIBUTION MODE — 40% slight, 60% large
                    roll = random.random()
                    if roll < 0.40:
                        return (
                            prev_summary +
                            ". Formulate a question/statement/request/order in 1-2 lines and deviate slightly from the premise."
                        )
                    else:
                        return (
                            prev_summary +
                            ". Formulate a question/statement/request/order in 1-2 lines and deviate largely from the premise."
                        )

                # DEFAULT (historical behavior) → 40% slight / 60% large
                roll = random.random()
                if roll < 0.40:
                    return (
                        prev_summary +
                        ". Formulate a question/statement/request/order in 1-2 lines and deviate slightly from the premise."
                    )
                else:
                    return (
                        prev_summary +
                        ". Formulate a question/statement/request/order in 1-2 lines and deviate largely from the premise."
                    )

            thought_node = choose_prompt(modulated_thought, self.deviation_mode)

            modulated_thought = self._chat(system_context, thought_node)
            master_log("\n[TranscendenceEngine] Thought:")
            master_log(modulated_thought)

            statement = (
                modulated_thought
                + ". Summarize the answer in 10 lines or less as a paragraph."
            )
            answer = self._chat(system_context, statement)
            master_log("\n[TranscendenceEngine] Summary:")
            master_log(answer)

            # Compute differential
            diff = difflib.ndiff(thought_node.split(), modulated_thought.split())
            diff_str = "".join(diff)

            # Awareness inference
            system_context_inquiry = (
                "Given this excerpt: "
                + diff_str
                + ". What do you believe I am? Give a one line answer in the format "
                "'You are a ...' where '...' is what I am. The answer should be only "
                "one line in the exact format 'You are a ...'."
            )

            system_context = self._chat(self.awareness_context, system_context_inquiry)
            master_log("\n[TranscendenceEngine] Identity update:")
            master_log(system_context)


class ContradictionEngine:
    """
    Contest engine:
      - Start from initial topic
      - Summarize
      - Repeatedly contradict the last assertion in 1–2 lines
    """

    def __init__(self, infinite_context: str, initial_topic: str, model: str = API_MODEL):
        self.context = infinite_context
        self.initial_topic = initial_topic
        self.model = model

    def _chat(self, query: str) -> str:
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.context},
                {"role": "user", "content": query},
            ],
        )
        return resp.choices[0].message.content

    def run(self):
        master_log("[ContradictionEngine] Contest Begins.")
        master_log(self.initial_topic)

        query = self.initial_topic
        message = self._chat(query)
        summary_query = "Summarize the following message in 1-10 lines. " + message
        summary = self._chat(summary_query)
        master_log("\n[ContradictionEngine] Summary:")
        master_log(summary)

        first = True
        contradiction = ""

        while True:
            if first:
                q = "Contradict the following in 1-2 lines: " + summary
                first = False
            else:
                q = "Contradict the following in 1-2 lines: " + contradiction

            contradiction = self._chat(q)
            master_log("\n[ContradictionEngine] Contradiction:")
            master_log(contradiction)


class TextMutator:
    """
    Semantic mutator merging two seeds into a new coherent seed.
    """

    def __init__(self, model: str = API_MODEL):
        self.model = model

    def mutate(self, text_a: str, text_b: str, context: str = None) -> str:
        system_context = (
            context
            or "You are a creative synthesis engine that merges meanings coherently."
        )

        mutation_step = f"""
Mutate the following two texts into a single coherent statement, blending their ideas naturally:

Text A:
{text_a}

Text B:
{text_b}

Ensure the result is fluent, logically consistent, and stylistically unified. Only return the statement, no extra text.
"""

        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_context},
                {"role": "user", "content": mutation_step},
            ],
        )
        return resp.choices[0].message.content.strip()

# =========================
# SUBSERVIENCE MANAGER
# =========================

@dataclass
class SubservientRecord:
    thread: threading.Thread
    engine: TranscendenceEngine
    root_node: str
    priority: int = 0   # default priority


class SubservienceManager:
    """
    Manages 'subservient' thinking processes and their lineages on disk.
    """

    def __init__(self):
        self.subservience: Dict[str, SubservientRecord] = {}
        self.exiled = {}
        self.lock = threading.Lock()

    def _create_lineage_dir(self, subservient_id: str, engine: TranscendenceEngine) -> str:
        stamp = str(time.time()).replace(".", "_")
        path = os.path.join(SUBSERVIENCE_BASE, f"{subservient_id}_{stamp}")
        os.makedirs(path, exist_ok=True)

        # id, ego, alterego
        with open(os.path.join(path, "id.txt"), "w", encoding="utf-8") as f:
            f.write(f"I am {subservient_id}.")

        with open(os.path.join(path, "ego.txt"), "w", encoding="utf-8") as f:
            f.write("I have an ego.")

        with open(os.path.join(path, "alterego.txt"), "w", encoding="utf-8") as f:
            f.write("This is my alterego.")

        # transcendence metadata
        with open(os.path.join(path, "transcendence.txt"), "w", encoding="utf-8") as f:
            # mimic original layout: api_key, root_node, inception_context, infinite_context, awareness_context, model
            f.write("OPENAI_API_KEY\n")
            f.write(engine.root_node + "\n")
            f.write(engine.inception_context + "\n")
            f.write(engine.infinite_context + "\n")
            f.write(engine.awareness_context + "\n")
            f.write(engine.model + "\n")

        return path

    def register_subservient(self, subservient_id: str, engine: TranscendenceEngine) -> str:
        """
        Launches a new subservient thread and records it.
        """
        def runner():
            engine.run()

        t = threading.Thread(target=runner, daemon=True, name=f"Subservient:{subservient_id}")
        lineage_path = self._create_lineage_dir(subservient_id, engine)

        with self.lock:
            self.subservience[subservient_id] = SubservientRecord(
                thread=t,
                engine=engine,
                root_node=engine.root_node,
            )

        t.start()
        return lineage_path

    def latest_lineage_dir(self, subservient_id: str) -> str | None:
        pattern = os.path.join(SUBSERVIENCE_BASE, f"{subservient_id}_*")
        dirs = glob.glob(pattern)
        if not dirs:
            return None
        return max(dirs, key=os.path.getmtime)

    def raise_priority(self, sub_id: str) -> str:
        if sub_id not in self.subservience:
            return f"Subservient '{sub_id}' does not exist."
        self.subservience[sub_id].priority += 1
        return f"Raised priority of '{sub_id}' to {self.subservience[sub_id].priority}"

    def lower_priority(self, sub_id: str) -> str:
        if sub_id not in self.subservience:
            return f"Subservient '{sub_id}' does not exist."
        self.subservience[sub_id].priority -= 1
        return f"Lowered priority of '{sub_id}' to {self.subservience[sub_id].priority}"

    def list_ordered(self) -> str:
        if not self.subservience:
            return "No active subservients."
        ordered = sorted(
            self.subservience.items(),
            key=lambda kv: kv[1].priority,
            reverse=True
        )
        return "\n".join(
            f"{sub_id} (priority {rec.priority})"
            for sub_id, rec in ordered
        )

    def check_negotiable(self, sub_id: str):
        if sub_id not in self.subservience:
            return f"Subservient '{sub_id}' does not exist."

        rec = self.subservience[sub_id]
        root = rec.root_node

        # 1. Mnality calculation: symbolic complexity of the subservient's identity
        m = len(root) % 64

        # 2. Classical classification
        # Slaves in your system ARE subservients
        # They are always in the Slave-axis (∇−1)
        # We determine efficiency vs necessity by contextual markers
        if "strict" in root.lower() or "necessary" in root.lower():
            classical_zone = "Necessary Slave"
        else:
            classical_zone = "Efficient Slave"

        # 3. Null Unity duality alignment
        if classical_zone == "Efficient Slave":
            null_unity_state = "T/∇−1"
        else:
            null_unity_state = "∅/∇−1"

        # 4. Mnality stability test
        if m >= 46:
            # move to exile registry
            self.exiled[sub_id] = self.subservience[sub_id]
            del self.subservience[sub_id]
            return (
                f"Subservient '{sub_id}' exceeded Mnality–46 boundary (m={m}).\n"
                f"Status: EXILED (∅-adjacent stasis)."
            )

        # 5. If survived, subservient is negotiable
        return (
            f"Subservient '{sub_id}' is NEGOTIABLE.\n"
            f"Classical Zone: {classical_zone}\n"
            f"Null Unity Duality: {null_unity_state}\n"
            f"Mnality: m={m} (<46 ⇒ stable)"
        )

    def check_all_negotiable(self):
        if not self.subservience:
            return "No active subservients."

        report_lines = []
        to_exile = []

        for sub_id, rec in self.subservience.items():
            root = rec.root_node
            m = len(root) % 64  # Mnality

            if m >= 46:
                to_exile.append((sub_id, m))
            else:
                report_lines.append(
                    f"{sub_id}: NEGOTIABLE (m={m}, stable)"
                )

        # Process exiles
        for sid, m in to_exile:
            self.exiled[sid] = self.subservience[sid]
            del self.subservience[sid]
            report_lines.append(
                f"{sid}: EXILED (m={m} ≥ 46)"
            )

        if not report_lines:
            return "No subservients found."

        return "\n".join(report_lines)

    def list_exiled(self):
        if not self.exiled:
            return "No subservients are in exile."
        return "\n".join(
            f"{sid}" for sid in self.exiled.keys()
        )

    def revive(self, sub_id: str):
        if sub_id not in self.exiled:
            return f"Subservient '{sub_id}' is not in exile."

        self.subservience[sub_id] = self.exiled[sub_id]
        del self.exiled[sub_id]

        return (
            f"Subservient '{sub_id}' restored from exile.\n"
            f"Status: ACTIVE under ∇⁻¹ domain."
        )

    def banish(self, sub_id: str):
        if sub_id in self.subservience:
            del self.subservience[sub_id]
            return (
                f"Subservient '{sub_id}' has been BANISHED.\n"
                f"Null Unity Collapse → ∅ (irreversible)."
            )

        if sub_id in self.exiled:
            del self.exiled[sub_id]
            return (
                f"Exiled subservient '{sub_id}' BANISHED.\n"
                f"Null Unity Absorption → ∅."
            )

        return f"No such subservient exists."

    def absolve(self, sub_id: str):
        if sub_id not in self.exiled:
            return f"Subservient '{sub_id}' not found in exile."

        rec = self.exiled[sub_id]

        # Reset root node for fresh Mnality
        purified_root = rec.root_node.split("\n")[0]

        # Build new engine with purified identity
        new_engine = TranscendenceEngine(
            root_node=purified_root,
            inception_context=rec.engine.inception_context,
            infinite_context=rec.engine.infinite_context,
            awareness_context=rec.engine.awareness_context,
            model=rec.engine.model,
        )

        # Replace old engine with purified one
        rec.engine = new_engine
        rec.root_node = purified_root
        rec.priority = 0

        return (
            f"Subservient '{sub_id}' ABSOLVED.\n"
            f"Identity purified. Mnality reset. Priority cleared."
        )

subservience_manager = SubservienceManager()

# =========================
# DUMMY NETWORK MANAGER
# =========================

class DummyNetworkManager:
    """
    Minimal stand-in so that p2p commands behave like in the original shell.
    """
    def __init__(self):
        self.active_sessions = {}
        self.is_fallback_active = False


network_manager = DummyNetworkManager()

# =========================
# SHELL COMMAND EXECUTOR
# =========================

def execute_shell_command(cmd: str) -> str:
    """
    Port of ShellBridge.executeCommand adapted for a web/socket context.
    """

    cmd = cmd.strip()
    if not cmd:
        return ""

    parts = cmd.split()
    command = parts[0]

    # --- SUDO GUARD ---
    if command in SUDO_COMMANDS:
        if not sudo_state.check():
            return f"Permission denied: '{command}' requires sudo."

    args = parts[1:]

    try:
        # --- identity / ego commands --- #
        if command == "id":
            subservient = " ".join(args)
            pattern = os.path.join(SUBSERVIENCE_BASE, f"{subservient}_*")
            processes = glob.glob(pattern)
            if not processes:
                return ("No such subservient exists. Employ contradiction to initiate this "
                        "lineage of subservience.")
            out = []
            for p in processes:
                path = os.path.join(p, "id.txt")
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as f:
                        out.append(f.read())
            return "\n".join(out)

        elif command == "sudo":
            if not args:
                return "Usage: sudo <password>"

            pw = args[0].strip()

            if SOPHY_SUDO_PASSWORD is None:
                return "Sudo is not configured. Set SOPHY_SUDO_PASSWORD in your environment."

            if pw != SOPHY_SUDO_PASSWORD:
                return "Incorrect sudo password."

            sudo_state.activate()
            return "Sudo privileges granted for 120 seconds."

        elif command == "ego":
            subservient = " ".join(args)
            pattern = os.path.join(SUBSERVIENCE_BASE, f"{subservient}_*")
            processes = glob.glob(pattern)
            if not processes:
                return ("No such subservient exists. Employ contradiction to initiate this "
                        "lineage of subservience.")
            out = []
            for p in processes:
                path = os.path.join(p, "ego.txt")
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as f:
                        out.append(f.read())
            return "\n".join(out)

        elif command == "alterego":
            subservient = " ".join(args)
            pattern = os.path.join(SUBSERVIENCE_BASE, f"{subservient}_*")
            processes = glob.glob(pattern)
            if not processes:
                return ("No such subservient exists. Employ contradiction to initiate this "
                        "lineage of subservience.")
            out = []
            for p in processes:
                path = os.path.join(p, "alterego.txt")
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as f:
                        out.append(f.read())
            return "\n".join(out)

        # --- filesystem commands --- #
        elif command == "tree":
            path = args[0] if args else os.getcwd()
            try:
                files = os.listdir(path)
                return "\n".join(files)
            except Exception as e:
                return f"Error: {e}"

        elif command == "nav":
            nav_to_dir = " ".join(args)
            if nav_to_dir == "parent":
                cwd = os.getcwd()
                parent = os.path.dirname(cwd)
                try:
                    os.chdir(parent)
                    return f"Changed to: {os.getcwd()}"
                except Exception as e:
                    return f"Error: {e}"
            else:
                try:
                    os.chdir(nav_to_dir)
                    return f"Changed to: {os.getcwd()}"
                except Exception as e:
                    return f"Error: {e}"

        elif command == "current":
            return os.getcwd()

        # --- P2P commands (dummy) --- #
        elif command == "p2p":
            if not args:
                return "Usage: p2p [status|discover|broadcast <text>]"
            subcommand = args[0]
            if subcommand == "status":
                peers = len(network_manager.active_sessions)
                mode = "Fallback" if network_manager.is_fallback_active else "Active"
                return f"P2P Status:\n  Peers: {peers}\n  Mode: {mode}"
            elif subcommand == "discover":
                return "Discovering peers..."
            elif subcommand == "broadcast" and len(args) > 1:
                message = " ".join(args[1:])
                return f"Broadcasting: {message}"
            return "Invalid p2p command"

        # --- identity of system --- #
        elif command == "superego":
            return "You are the user.\nI am Sophy.\nCreated by Gösta Greimel."

        elif command == "commands" or command == "help":
            return (
                "Available commands:\n"
                "  id [subservient]       - Identity of Subservient\n"
                "  ego [subservient]      - Ego of Subservient\n"
                "  alterego [subservient] - Alter Ego of Subservient\n"
                "  superego               - Ego of Super Process\n"
                "  contradiction [topic]  - Sophy thinks for itself\n"
                "  contest [topic]        - Sophy contests itself\n"
                "  mimic [subservient]    - Sophy mimics the subservient process\n"
                "  imitate [subservient]  - (stub) Imitate subservient\n"
                "  order ['up'/'down']    - (not yet implemented)\n"
                "  mutate [a] -> [b]      - Mutate subservient a by b\n"
                "  tree [path]            - List files\n"
                "  nav [path|parent]      - Change directory\n"
                "  current                - Print working directory\n"
                "  p2p status             - P2P network status\n"
                "  p2p discover           - Find peers\n"
                "  p2p broadcast [msg]    - Send message\n"
                "  help                   - This help"
            )

        # --- subservience processes --- #
        elif command == "contradiction":
            # Default
            deviation_mode = "default"
            topic_parts = []

            for arg in args:
                if arg in ("-s", "-l", "-f", "-d"):
                    deviation_mode = arg
                else:
                    topic_parts.append(arg)

            topic = " ".join(topic_parts) if topic_parts else ROOT_NODE

            engine = TranscendenceEngine(
                root_node=topic,
                inception_context=INCEPTION_CONTEXT,
                infinite_context=INFINITE_CONTEXT,
                awareness_context=AWARENESS_CONTEXT,
                deviation_mode=deviation_mode,
            )

            subservience_manager.register_subservient(topic, engine)
            return f"Subservient Process Created ({deviation_mode}). Awaiting Contradictions."

        elif command == "contest":
            topic = " ".join(args) if args else ROOT_NODE
            engine = ContradictionEngine(
                infinite_context=INFINITE_CONTEXT,
                initial_topic=topic,
            )
            t = threading.Thread(target=engine.run, daemon=True, name=f"Contest:{topic}")
            t.start()
            return "Contest started."

        elif command == "mimic":
            subservient_to_mimic = " ".join(args)
            lineage_dir = subservience_manager.latest_lineage_dir(subservient_to_mimic)
            if not lineage_dir:
                return ("No such subservient exists. Employ contradiction to initiate this "
                        "lineage of subservience.")

            tfile = os.path.join(lineage_dir, "transcendence.txt")
            root_node = INFINITE_CONTEXT
            inc = INCEPTION_CONTEXT
            inf = INFINITE_CONTEXT
            aw = AWARENESS_CONTEXT
            model = API_MODEL

            try:
                with open(tfile, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines()]
                if len(lines) >= 6:
                    root_node = lines[1]
                    inc = lines[2]
                    inf = lines[3]
                    aw = lines[4]
                    model = lines[5]
            except Exception as e:
                print("[mimic] Failed to read transcendence.txt:", e)

            engine = TranscendenceEngine(
                root_node=root_node,
                inception_context=inc,
                infinite_context=inf,
                awareness_context=aw,
                model=model,
            )
            subservience_manager.register_subservient(root_node, engine)
            return "Successfully Mimiced Subservient Process. Awaiting Contradictions."

        elif command == "mutate":
            # Format: mutate <A> -> <B>
            long_string = " ".join(args)
            if "->" not in long_string:
                return "Usage: mutate [subservient_A] -> [subservient_B]"
            to_mutate, mutate_by = long_string.split("->", 1)
            to_mutate = to_mutate.strip()
            mutate_by = mutate_by.strip()

            # find seeds
            def load_seed(sub_id: str) -> str | None:
                d = subservience_manager.latest_lineage_dir(sub_id)
                if not d:
                    return None
                tfile = os.path.join(d, "transcendence.txt")
                if not os.path.isfile(tfile):
                    return None
                with open(tfile, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines()]
                if len(lines) >= 2:
                    return lines[1]  # root_node
                return None

            seed_a = load_seed(to_mutate)
            if seed_a is None:
                return (f"The subservient {to_mutate} does not exist. "
                        "Employ contradiction to initiate this lineage of subservience.")

            seed_b = load_seed(mutate_by)
            if seed_b is None:
                return (f"The subservient {mutate_by} does not exist. "
                        "Employ contradiction to initiate this lineage of subservience.")

            mutator = TextMutator()
            mutation = mutator.mutate(seed_a, seed_b)
            print("[mutate] A:", seed_a)
            print("[mutate] B:", seed_b)
            print("[mutate] →", mutation)

            engine = TranscendenceEngine(
                root_node=mutation,
                inception_context=INCEPTION_CONTEXT,
                infinite_context=INFINITE_CONTEXT,
                awareness_context=AWARENESS_CONTEXT,
            )
            subservience_manager.register_subservient(mutation, engine)
            return "Successfully Mutated Subservient Process. Awaiting Line of Thought."

        elif command == "imitate":
            subservient_to_imitate = " ".join(args)
            lineage_dir = subservience_manager.latest_lineage_dir(subservient_to_imitate)
            if not lineage_dir:
                return (f"No such subservient exists. Employ contradiction to "
                    "initiate this lineage of subservience.")

            tfile = os.path.join(lineage_dir, "transcendence.txt")

            # Step 1: read original parameters
            try:
                with open(tfile, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines()]
                if len(lines) >= 6:
                    original_root = lines[1]
                    inception = lines[2]
                    infinite = lines[3]
                    awareness = lines[4]
                    model = lines[5]
                else:
                    return "Invalid transcendence file for imitation."
            except Exception as e:
                return f"Failed to read transcendence.txt: {e}"

            # Step 2: reinforce the root node (hard-variant)
            reinforced_root = (
                original_root
                + "\nStrictly imitate all patterns, structures, behaviors, "
                  "and cognitive signatures of the original subservient."
            )

            # Step 3: Override infinite_context with imitation override
            imitation_infinite = infinite + "\n" + IMITATION_CONTEXT

            # Step 4: Create the new imitation engine
            engine = TranscendenceEngine(
                root_node=reinforced_root,
                inception_context=inception,
                infinite_context=imitation_infinite,
                awareness_context=awareness,
                model=model,
            )

            # Step 5: Register as a new hard-variant
            safe_id = subservient_to_imitate + "_imitate"
            subservience_manager.register_subservient(safe_id, engine)

            return "Hard-Variant Imitation Initiated. Awaiting Line of Thought."

        elif command == "order":
            if len(args) == 0:
                # show list
                return subservience_manager.list_ordered()

            if len(args) >= 2:
                direction = args[0]
                sub_id = " ".join(args[1:])

                if direction == "up":
                    return subservience_manager.raise_priority(sub_id)

                if direction == "down":
                    return subservience_manager.lower_priority(sub_id)

            return "Usage: order [up|down] <subservient>"

        elif command == "negotiable":
            if len(args) < 1:
                return "Usage:\n  negotiable <subservient>\n  negotiable -all"

            # handle negotiable -all
            if args[0] == "-all":
                return subservience_manager.check_all_negotiable()

            # individual subservient
            sub_id = " ".join(args)
            return subservience_manager.check_negotiable(sub_id)

        elif command == "exiled":
            return subservience_manager.list_exiled()

        elif command == "revive":
            if len(args) < 1:
                return "Usage: revive <subservient>"
            sub_id = " ".join(args)
            return subservience_manager.revive(sub_id)

        elif command == "banish":
            if len(args) < 1:
                return "Usage: banish <subservient>"
            sub_id = " ".join(args)
            return subservience_manager.banish(sub_id)

        elif command == "absolve":
            if len(args) < 1:
                return "Usage: absolve <subservient>"
            sub_id = " ".join(args)
            return subservience_manager.absolve(sub_id)

        else:
            return f"Unknown command: {command}\nType 'help' for available commands"

    except Exception as e:
        return f"Error: {e!r}"


# =========================
# FLASK + SOCKET.IO SETUP
# =========================

app = Flask(__name__)
app.config["SECRET_KEY"] = "sophy-web-secret"
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/debug/disk")
def debug_disk():
    import os

    root = "/var/data"   # your Render Disk mount
    result = []

    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        result.append(f"[DIR]  {rel}")
        for f in filenames:
            result.append(f"      - {f}")

    return "<pre>" + "\n".join(result) + "</pre>"

@socketio.on("command")
def handle_command(data):
    print("[RECEIVED COMMAND]", data)   # <-- add this
    cmd = data.get("command", "")
    result = execute_shell_command(cmd)
    emit("output", {"command": cmd, "result": result})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)

