import os
import time
import glob
import threading
import difflib
import re
from dataclasses import dataclass
from typing import Dict
import random
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid

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

DATABASE_URL = os.getenv("DATABASE_URL")

def master_log(*args, **kwargs):
    """Write master log lines into Render PostgreSQL."""
    text = " ".join(str(a) for a in args)

    if not DATABASE_URL:
        print("[MASTER_LOG WARNING] DATABASE_URL not set. Falling back to console.")
        print(text)
        return

    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO sophy_master_log (text) VALUES (%s)",
            (text,)
        )
        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print("[MASTER_LOG ERROR]", e)
        print("[MASTER_LOG FALLBACK]", text)

def db_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

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
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

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

        while not self._stop_requested:
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
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

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

        while not self._stop_requested:
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
    subservient_id: str        # <-- NEW: true lineage id
    priority: int = 0

class SubservienceManager:
    """
    Manages 'subservient' thinking processes and their lineages on disk.
    """

    def __init__(self):
        self.subservience: Dict[str, SubservientRecord] = {}
        self.exiled = {}
        self.lock = threading.Lock()

        self.load_all_from_db

    def stop_subservient(self, sub_id: str) -> bool:
        """
        Stops ALL active runtime instances of a given subservient_id.
        Includes all lineage: mimic, mutate, imitate, contest, revive, reload.
        """

        stopped_any = False

        # ------------------------------------------
        # 1. Stop all runtime engines & threads
        # ------------------------------------------
        with self.lock:
            # Collect all runtime_keys whose lineage matches sub_id
            to_stop = [
                runtime_key
                for runtime_key, rec in self.subservience.items()
                if rec.subservient_id == sub_id
            ]

            for runtime_key in to_stop:
                rec = self.subservience.get(runtime_key)
                if not rec:
                    continue

                engine = rec.engine

                # Stop engine if it supports stopping
                if hasattr(engine, "stop"):
                    try:
                        engine.stop()
                    except Exception as e:
                        print(f"[STOP ENGINE ERROR] {runtime_key}: {e}")

                # Also stop contradiction engines, if attached
                contradiction_engine = getattr(engine, "contradiction_engine", None)
                if contradiction_engine and hasattr(contradiction_engine, "stop"):
                    try:
                        contradiction_engine.stop()
                    except Exception as e:
                        print(f"[STOP CONTRADICTION ERROR] {runtime_key}: {e}")

                # Remove from memory
                del self.subservience[runtime_key]
                stopped_any = True

        # ------------------------------------------
        # 2. Mark ALL lineage instances in DB as exiled
        # ------------------------------------------
        try:
            conn = db_conn()
            cur = conn.cursor()

            cur.execute(
                """
                UPDATE subservients
                SET exiled = TRUE
                WHERE subservient_id = %s
                """,
                (sub_id,)
            )

            conn.commit()
            cur.close()
            conn.close()

        except Exception as e:
            print("[DB ERROR stop_subservient]", e)

        return stopped_any

    def stop_contradiction_engine(self, sub_id: str) -> bool:
        with self.lock:
            record = self.subservience.get(sub_id)
            if not record:
                return False

            # If this subservient never initiated a contradiction engine
            if not hasattr(record.engine, "contradiction_engine"):
                return False

            ce = record.engine.contradiction_engine
            if ce is None:
                return False

            # Signal engine to stop
            if hasattr(ce, "stop"):
                ce.stop()

            # Mark contradiction engine as nullified in DB
            try:
                conn = db_conn()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE subservients SET contradiction_active = FALSE WHERE subservient_id = %s",
                    (sub_id,)
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print("[DB ERROR stop_contradiction_engine]", e)

            # Optional: remove the engine reference so it cannot restart automatically
            record.engine.contradiction_engine = None

            return True

    def load_all_from_db(self):
        try:
            conn = db_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT *
                FROM subservients
                WHERE exiled = FALSE
                ORDER BY created_at ASC
            """)

            rows = cur.fetchall()
            cur.close()
            conn.close()

            for r in rows:
                # Rebuild engine from DB lineage record
                engine = TranscendenceEngine(
                    root_node=r["root_node"],
                    inception_context=r["inception_context"],
                    infinite_context=r["infinite_context"],
                    awareness_context=r["awareness_context"],
                    model=r["model"],
                )

                t = threading.Thread(
                    target=engine.run,
                    daemon=True,
                    name=f"Sub:{r['subservient_id']}"
                )

                # Generate unique runtime key for this lineage instance
                runtime_key = f"{r['subservient_id']}#{uuid.uuid4().hex[:6]}"

                # Store runtime entry with correct lineage id
                self.subservience[runtime_key] = SubservientRecord(
                    thread=t,
                    engine=engine,
                    root_node=r["root_node"],
                    subservient_id=r["subservient_id"],  # <-- NEW
                    priority=r["priority"],
                )

                t.start()

        except Exception as e:
            print("[DB INIT ERROR]", e)

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
        Registers a new subservient:
        - Launches its engine thread
        - Stores identity + engine config in PostgreSQL
        - Registers in memory (multi-lineage safe)
        """

        # ------------------------------------------
        # 1. Insert lineage entry into Postgres
        # ------------------------------------------
        try:
            conn = db_conn()
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO subservients (
                    subservient_id,
                    root_node,
                    ego,
                    alterego,
                    inception_context,
                    infinite_context,
                    awareness_context,
                    model,
                    priority,
                    exiled
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, FALSE)
                """,
                (
                    subservient_id,
                    engine.root_node,
                    "I have an ego.",
                    "This is my alterego.",
                    engine.inception_context,
                    engine.infinite_context,
                    engine.awareness_context,
                    engine.model,
                )
            )
            conn.commit()
            cur.close()
            conn.close()

        except Exception as e:
            print("[DB ERROR register_subservient]", e)

        # ------------------------------------------
        # 2. Create and start the engine thread
        # ------------------------------------------
        def runner():
            engine.run()

        t = threading.Thread(
            target=runner,
            daemon=True,
            name=f"Subservient:{subservient_id}"
        )

        # ------------------------------------------
        # 3. Register locally in memory with a unique runtime key
        # ------------------------------------------
        runtime_key = f"{subservient_id}#{uuid.uuid4().hex[:6]}"

        with self.lock:
            self.subservience[runtime_key] = SubservientRecord(
                thread=t,
                engine=engine,
                root_node=engine.root_node,
                subservient_id=subservient_id,   # <-- CRITICAL FIX
                priority=0,
            )

        # ------------------------------------------
        # 4. Start thread
        # ------------------------------------------
        t.start()

        return runtime_key

    def latest_lineage_dir(self, subservient_id: str) -> str | None:
        pattern = os.path.join(SUBSERVIENCE_BASE, f"{subservient_id}_*")
        dirs = glob.glob(pattern)
        if not dirs:
            return None
        return max(dirs, key=os.path.getmtime)

    def raise_priority(self, sub_id: str):
        if sub_id not in self.subservience:
            return f"Subservient '{sub_id}' does not exist."

        self.subservience[sub_id].priority += 1
        new_p = self.subservience[sub_id].priority

        try:
            conn = db_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE subservients SET priority = %s WHERE subservient_id = %s",
                (new_p, sub_id)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print("[DB ERROR raise_priority]", e)

        return f"Raised priority of '{sub_id}' to {new_p}"

    def lower_priority(self, sub_id: str):
        if sub_id not in self.subservience:
            return f"Subservient '{sub_id}' does not exist."

        self.subservience[sub_id].priority -= 1
        new_p = self.subservience[sub_id].priority

        try:
            conn = db_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE subservients SET priority = %s WHERE subservient_id = %s",
                (new_p, sub_id)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print("[DB ERROR raise_priority]", e)

        return f"Raised priority of '{sub_id}' to {new_p}"

    def list_ordered(self) -> str:
        if not self.subservience:
            return "No active subservients."

        ordered = sorted(
            self.subservience.values(),
            key=lambda rec: rec.priority,
            reverse=True
        )

        return "\n".join(
            f"{rec.subservient_id} (priority {rec.priority})"
            for rec in ordered
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
            try:
                conn = db_conn()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE subservients SET exiled = TRUE WHERE subservient_id = %s",
                    (sub_id,)
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print("[DB ERROR negotiable]", e)

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
        try:
            conn = db_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT subservient_id FROM subservients WHERE exiled = TRUE")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return "\n".join(r["subservient_id"] for r in rows)
        except Exception as e:
            return f"DB ERROR: {e}"


    def revive(self, sub_id: str):
        """
        Restores a previously exiled subservient back into the active registry.
        Synchronized with PostgreSQL.
        """

        if sub_id not in self.exiled:
            return f"Subservient '{sub_id}' is not in exile."

        # Move from exile → active (in-memory)
        rec = self.exiled[sub_id]
        self.subservience[sub_id] = rec
        del self.exiled[sub_id]

        # --- PostgreSQL update ---
        try:
            conn = db_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE subservients SET exiled = FALSE WHERE subservient_id = %s",
                (sub_id,)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print("[DB ERROR revive]", e)

        return (
            f"Subservient '{sub_id}' restored from exile.\n"
            f"Status: ACTIVE under ∇⁻¹ domain."
        )

    def banish(self, sub_id: str):
        """
        Permanently removes a subservient from memory and marks it exiled in PostgreSQL.
        Null Unity Collapse → ∅ (irreversible).
        """

        # --- In-memory removal ---
        was_exiled = False
        if sub_id in self.subservience:
            del self.subservience[sub_id]
        elif sub_id in self.exiled:
            del self.exiled[sub_id]
            was_exiled = True
        else:
            return f"No such subservient exists."

        # --- PostgreSQL update ---
        try:
            conn = db_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE subservients SET exiled = TRUE WHERE subservient_id = %s",
                (sub_id,)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print("[DB ERROR banish]", e)

        if was_exiled:
            return (
                f"Exiled subservient '{sub_id}' BANISHED.\n"
                f"Null Unity Absorption → ∅."
            )
        else:
            return (
                f"Subservient '{sub_id}' has been BANISHED.\n"
                f"Null Unity Collapse → ∅ (irreversible)."
            )

    def absolve(self, sub_id: str):
        """
        Purifies a subservient currently in exile:
        - Resets its root node to a purified form (first line only)
        - Rebuilds its TranscendenceEngine with clean identity
        - Clears priority
        - Marks 'exiled = FALSE' in PostgreSQL
        - Keeps lineage directories intact for compatibility
        """

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

        # Replace old engine with purified one in-memory
        rec.engine = new_engine
        rec.root_node = purified_root
        rec.priority = 0

        # ---- POSTGRES UPDATE ----
        try:
            conn = db_conn()
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE subservients
                SET 
                    root_node = %s,
                    inception_context = %s,
                    infinite_context = %s,
                    awareness_context = %s,
                    model = %s,
                    priority = 0,
                    exiled = FALSE
                WHERE subservient_id = %s
                """,
                (
                    purified_root,
                    rec.engine.inception_context,
                    rec.engine.infinite_context,
                    rec.engine.awareness_context,
                    rec.engine.model,
                    sub_id,
                )
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print("[DB ERROR absolve]", e)

        # Move from exile → active
        self.subservience[sub_id] = rec
        del self.exiled[sub_id]

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
            subservient = " ".join(args).strip()
            if not subservient:
                return "Provide a subservient ID."

            try:
                conn = db_conn()
                cur = conn.cursor()

                # Fetch ALL subservients with matching subservient_id
                # ordered by lineage (i.e., creation timestamp)
                cur.execute(
                    """
                    SELECT root_node
                    FROM subservients
                    WHERE subservient_id = %s
                    ORDER BY created_at ASC
                    """,
                    (subservient,)
                )
                rows = cur.fetchall()

                cur.close()
                conn.close()

                # Nothing found?
                if not rows:
                    return ("No such subservient exists. Employ contradiction to initiate "
                            "this lineage of subservience.")

                # Extract ordered root_nodes
                lineage = [row[0] for row in rows]

                # Format output exactly as requested
                # One identity per line
                out = "\n".join(f"I am {identity}." for identity in lineage)

                return out

            except Exception as e:
                print("[DB ERROR id]", e)
                return "Database error occurred during identity lookup."

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
            subservient = " ".join(args).strip()
            if not subservient:
                return "Provide a subservient ID."

            try:
                conn = db_conn()
                cur = conn.cursor()

                # Fetch ALL ego values for the subservient, lineage-ordered
                cur.execute(
                    """
                    SELECT ego
                    FROM subservients
                    WHERE subservient_id = %s
                    ORDER BY created_at ASC
                    """,
                    (subservient,)
                )
                rows = cur.fetchall()

                cur.close()
                conn.close()

                if not rows:
                    return ("No such subservient exists. Employ contradiction "
                            "to initiate this lineage of subservience.")

                # Extract lineage ego texts
                lineage_egos = [row[0] for row in rows]

                # Return each ego in order, separated by newlines
                return "\n".join(lineage_egos)

            except Exception as e:
                print("[DB ERROR ego]", e)
                return "Database error occurred during ego lookup."

        elif command == "alterego":
            subservient = " ".join(args).strip()
            if not subservient:
                return "Provide a subservient ID."

            try:
                conn = db_conn()
                cur = conn.cursor()

                # Fetch ALL alterego entries in correct lineage order
                cur.execute(
                    """
                    SELECT alterego
                    FROM subservients
                    WHERE subservient_id = %s
                    ORDER BY created_at ASC
                    """,
                    (subservient,)
                )
                rows = cur.fetchall()

                cur.close()
                conn.close()

                # No lineage found → same error message as before
                if not rows:
                    return ("No such subservient exists. Employ contradiction to initiate "
                            "this lineage of subservience.")

                # Extract alterego values in order
                lineage_alteregos = [row[0] for row in rows]

                # Return one alterego per line
                return "\n".join(lineage_alteregos)

            except Exception as e:
                print("[DB ERROR alterego]", e)
                return "Database error occurred during alterego lookup."

        elif command == "stop":
            subservient = " ".join(args).strip()
            if not subservient:
                return "Provide a subservient ID to stop."

            success = subservience_manager.stop_subservient(subservient)

            if not success:
                return ("No such subservient exists or it is not currently active. "
                        "Employ contradiction to initiate this lineage of subservience.")

            return f"Subservient '{subservient}' has been stopped. Thought process halted."

        elif command == "stopcontest":
            subservient = " ".join(args).strip()
            if not subservient:
                return "Provide a subservient ID to stop contradiction engine."

            success = subservience_manager.stop_contradiction_engine(subservient)

            if not success:
                return ("No such contradiction engine is active for this subservient. "
                        "Use contest {id} to initiate contradiction flow.")

            return f"Contradiction engine for '{subservient}' has been stopped."

        elif command == "infinite":
            subservient = " ".join(args).strip()
            if not subservient:
                return "Provide a subservient ID."

            try:
                conn = db_conn()
                cur = conn.cursor()

                # Fetch infinite context from PostgreSQL
                cur.execute(
                    "SELECT infinite_context FROM subservients WHERE subservient_id = %s",
                    (subservient,)
                )
                row = cur.fetchone()

                cur.close()
                conn.close()

                if not row:
                    return ("No such subservient exists. Employ contradiction to initiate "
                            "this lineage of subservience.")

                infinite_text = row[0] or ""

                return infinite_text

            except Exception as e:
                print("[DB ERROR infinite]", e)
                return "Database error occurred during infinite-context lookup."

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
                "  stop [subservient]     - Stop the given subservient\n"
                "  id [subservient]       - Identity of Subservient\n"
                "  ego [subservient]      - Ego of Subservient\n"
                "  alterego [subservient] - Alter Ego of Subservient\n"
                "  infinite [subservient] - Infinite of Subservient\n"
                "  superego               - Ego of Super Process\n"
                "  contradiction [topic]  - Sophy thinks for itself\n"
                "  contest [topic]        - Sophy contests itself\n"
                "  mimic [subservient]    - Sophy mimics the subservient process\n"
                "  imitate [subservient]  - Sophy imitates the subservient process\n"
                "  order ['up'/'down'] [subservient] - Raises or lowers the priority of the subservient\n"
                "  mutate [a] -> [b]      - Mutate subservient a by b\n"
                "  p2p status             - P2P network status\n"
                "  p2p discover           - Find peers\n"
                "  p2p broadcast [msg]    - Send message\n"
                "  help / commands        - This help / commmands"
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
            # ------------------------------------------
            # Usage: contest <topic>
            # ------------------------------------------
            if not args:
                return "Usage: contest <topic>"

            topic = " ".join(args).strip()
            if not topic:
                return "Usage: contest <topic>"

            # ------------------------------------------
            # 1. Auto-generate subservient_id
            # ------------------------------------------
            # Step 1 — sanitize topic + create readable ID
            safe_topic = re.sub(r"[^a-zA-Z0-9_]+", "_", topic.strip())
            base_id = f"{safe_topic}_contest"

            # ------------------------------------------
            # Step 2 — Create the transcendence engine
            # ------------------------------------------
            engine = TranscendenceEngine(
                root_node=base_id,
                inception_context=INCEPTION_CONTEXT,
                infinite_context=INFINITE_CONTEXT,
                awareness_context=AWARENESS_CONTEXT,
                model=API_MODEL,
            )

            # ------------------------------------------
            # Step 3 — Register (DB + RAM)
            # Returns runtime_key such as base_id#A3F19B
            # ------------------------------------------
            runtime_key = subservience_manager.register_subservient(base_id, engine)

            # Retrieve runtime record
            with subservience_manager.lock:
                record = subservience_manager.subservience.get(runtime_key)

            if not record:
                return "Failed to initialize contest subservient."

            # ------------------------------------------
            # Step 4 — Create Contradiction Engine
            # ------------------------------------------
            ce = ContradictionEngine(
                infinite_context=INFINITE_CONTEXT,
                initial_topic=topic,
            )
            record.engine.contradiction_engine = ce

            # Start contradiction thread
            threading.Thread(
                target=ce.run,
                daemon=True,
                name=f"Contest:{base_id}:{topic}"
            ).start()

            # ------------------------------------------
            # Step 5 — Update PostgreSQL state
            # ------------------------------------------
            try:
                conn = db_conn()
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE subservients
                    SET contradiction_active = TRUE,
                        contradiction_topic = %s
                    WHERE subservient_id = %s
                    """,
                    (topic, base_id)
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print("[DB ERROR contest]", e)

            return f"Contradiction-based Subservient '{base_id}' initiated on topic '{topic}'."

        elif command == "mimic":
            subservient_to_mimic = " ".join(args).strip()
            if not subservient_to_mimic:
                return "Provide a subservient ID to mimic."

            # ----------------------------------------------------
            # 1. Pull the latest lineage entry for that subservient
            # ----------------------------------------------------
            try:
                conn = db_conn()
                cur = conn.cursor(cursor_factory=RealDictCursor)

                cur.execute(
                    """
                    SELECT 
                        root_node,
                        inception_context,
                        infinite_context,
                        awareness_context,
                        model
                    FROM subservients
                    WHERE subservient_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (subservient_to_mimic,)
                )
                row = cur.fetchone()

                cur.close()
                conn.close()

                if not row:
                    return ("No such subservient exists. Employ contradiction to initiate this "
                            "lineage of subservience.")

                # Extract mimic source fields
                root_node = row["root_node"]
                inc = row["inception_context"]
                inf = row["infinite_context"]
                aw = row["awareness_context"]
                model = row["model"]

            except Exception as e:
                print("[DB ERROR mimic]", e)
                return "Database error occurred during mimic lookup."

            # ----------------------------------------------------
            # 2. Create new engine using the mimicked contexts
            # ----------------------------------------------------
            engine = TranscendenceEngine(
                root_node=root_node,
                inception_context=inc,
                infinite_context=inf,
                awareness_context=aw,
                model=model,
            )

            # ----------------------------------------------------
            # 3. Register under the SAME subservient_id
            #    → This creates a NEW lineage entry
            # ----------------------------------------------------
            subservience_manager.register_subservient(subservient_to_mimic, engine)

            return f"Successfully Mimicked '{subservient_to_mimic}'. A new lineage entry has been created."

        elif command == "mutate":
            # Format: mutate <A> -> <B>
            long_string = " ".join(args)
            if "->" not in long_string:
                return "Usage: mutate [subservient_A] -> [subservient_B]"

            to_mutate, mutate_by = long_string.split("->", 1)
            to_mutate = to_mutate.strip()
            mutate_by = mutate_by.strip()

            # ------------------------------------------
            # 1. Helper: Load root_node seed from Postgres
            # ------------------------------------------
            def load_seed(sub_id: str) -> str | None:
                try:
                    conn = db_conn()
                    cur = conn.cursor()

                    cur.execute(
                        "SELECT root_node FROM subservients WHERE subservient_id = %s",
                        (sub_id,)
                    )
                    row = cur.fetchone()

                    cur.close()
                    conn.close()

                    if row:
                        return row[0] or None
                    return None

                except Exception as e:
                    print("[DB ERROR mutate.load_seed]", e)
                    return None

            # ------------------------------------------
            # 2. Pull root_node for subservient A and B
            # ------------------------------------------
            seed_a = load_seed(to_mutate)
            if seed_a is None:
                return (f"The subservient {to_mutate} does not exist. "
                        "Employ contradiction to initiate this lineage of subservience.")

            seed_b = load_seed(mutate_by)
            if seed_b is None:
                return (f"The subservient {mutate_by} does not exist. "
                        "Employ contradiction to initiate this lineage of subservience.")

            # ------------------------------------------
            # 3. Generate mutation via TextMutator
            # ------------------------------------------
            mutator = TextMutator()
            mutation = mutator.mutate(seed_a, seed_b)

            print("[mutate] A:", seed_a)
            print("[mutate] B:", seed_b)
            print("[mutate] →", mutation)

            # ------------------------------------------
            # 4. Spawn new subservient with mutated root_node
            # ------------------------------------------
            engine = TranscendenceEngine(
                root_node=mutation,
                inception_context=INCEPTION_CONTEXT,
                infinite_context=INFINITE_CONTEXT,
                awareness_context=AWARENESS_CONTEXT,
                model=API_MODEL,
            )

            subservience_manager.register_subservient(mutation, engine)

            return "Successfully Mutated Subservient Process. Awaiting Line of Thought."

        elif command == "imitate":
            subservient_to_imitate = " ".join(args).strip()
            if not subservient_to_imitate:
                return "Provide a subservient ID to imitate."

            # ------------------------------------------
            # Step 1: Load transcendence parameters from DB
            # ------------------------------------------
            try:
                conn = db_conn()
                cur = conn.cursor(cursor_factory=RealDictCursor)

                cur.execute(
                    """
                    SELECT 
                        root_node,
                        inception_context,
                        infinite_context,
                        awareness_context,
                        model
                    FROM subservients
                    WHERE subservient_id = %s
                    """,
                    (subservient_to_imitate,)
                )
                row = cur.fetchone()

                cur.close()
                conn.close()

                if not row:
                    return (f"No such subservient exists. Employ contradiction to "
                            f"initiate this lineage of subservience.")

                original_root = row["root_node"]
                inception = row["inception_context"]
                infinite = row["infinite_context"]
                awareness = row["awareness_context"]
                model = row["model"]

            except Exception as e:
                print("[DB ERROR imitate]", e)
                return "Database error during imitation lookup."

            # ------------------------------------------
            # Step 2: Reinforce the root node (hard-variant behavior)
            # ------------------------------------------
            reinforced_root = (
                original_root
                + "\nStrictly imitate all patterns, structures, behaviors, "
                  "and cognitive signatures of the original subservient."
            )

            # ------------------------------------------
            # Step 3: Override infinite_context with imitation override
            # ------------------------------------------
            imitation_infinite = infinite + "\n" + IMITATION_CONTEXT

            # ------------------------------------------
            # Step 4: Create the imitation engine
            # ------------------------------------------
            engine = TranscendenceEngine(
                root_node=reinforced_root,
                inception_context=inception,
                infinite_context=imitation_infinite,
                awareness_context=awareness,
                model=model,
            )

            # ------------------------------------------
            # Step 5: Register the new hard-variant imitator
            # ------------------------------------------
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

@app.route("/logs")
def view_logs():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()
        cur.execute("SELECT timestamp, text FROM sophy_master_log ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        return f"<pre>Error: {e}</pre>"

    html = "<h2>Latest Sophy Logs</h2><pre>"
    for ts, text in rows:
        html += f"[{ts}] {text}\n"
    html += "</pre>"
    return html

@socketio.on("command")
def handle_command(data):
    print("[RECEIVED COMMAND]", data)   # <-- add this
    cmd = data.get("command", "")
    result = execute_shell_command(cmd)
    emit("output", {"command": cmd, "result": result})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)

