"""Solana RPC helpers for Ore miner."""

import base64
import json
import os
import struct
from typing import Dict, List

try:
    from solana.rpc.api import Client  # type: ignore
    from solders.pubkey import Pubkey  # type: ignore
    _SOLANA_AVAILABLE = True
except ModuleNotFoundError:
    Client = None  # type: ignore[assignment]
    Pubkey = None  # type: ignore[assignment]
    _SOLANA_AVAILABLE = False

# ---------- CONFIG ----------
RPC_URL = "http://va.pixellabz.io/"  # use your Frankfurt RPC or fallback later
ORE_PROGRAM_ID = "oreV3EG1i9BEgiAJ8b177Z2S2rMarzak4NMv1kULvWv"
# ----------------------------

client = Client(RPC_URL) if _SOLANA_AVAILABLE else None


# Round struct (from round.rs)
def _parse_round(data: bytes) -> Dict:
    off = 0
    unpack_u64 = lambda b, i: struct.unpack_from("<Q", b, i)[0]

    rid = unpack_u64(data, off); off += 8
    deployed = [unpack_u64(data, off + i * 8) for i in range(25)]; off += 25 * 8
    slot_hash = data[off:off+32]; off += 32
    counts = [unpack_u64(data, off + i * 8) for i in range(25)]; off += 25 * 8

    expires_at = unpack_u64(data, off); off += 8
    motherlode = unpack_u64(data, off); off += 8
    rent_payer = data[off:off+32]; off += 32
    top_miner = data[off:off+32]; off += 32

    top_miner_reward = unpack_u64(data, off); off += 8
    total_deployed = unpack_u64(data, off); off += 8
    total_vaulted = unpack_u64(data, off); off += 8
    total_winnings = unpack_u64(data, off); off += 8

    return {
        "id": rid,
        "deployed": deployed,
        "slot_hash": slot_hash,
        "counts": counts,
        "expires_at": expires_at,
        "motherlode": motherlode,
        "top_miner_reward": top_miner_reward,
        "total_deployed": total_deployed,
        "total_vaulted": total_vaulted,
        "total_winnings": total_winnings,
    }


def _get_all_round_accounts() -> List[Dict]:
    """Fetch all ORE round accounts safely from the RPC."""

    if not _SOLANA_AVAILABLE or client is None or Pubkey is None:
        print("[WARN] Solana client unavailable; returning no round data.")
        return []

    try:
        resp = client.get_program_accounts(Pubkey.from_string(ORE_PROGRAM_ID))
    except Exception as e:  # pragma: no cover - defensive logging
        print(f"[ERROR] RPC call failed: {e}")
        return []

    if resp.value is None:
        print("[WARN] RPC returned no data.")
        return []

    rounds = []
    for acc in resp.value:
        data_field = acc.account.data
        raw = None

        # --- Handle all Solana formats ---
        if isinstance(data_field, (tuple, list)) and len(data_field) > 0:
            try:
                raw = base64.b64decode(data_field[0])
            except Exception as e:  # pragma: no cover - defensive logging
                print(f"[ERROR] Base64 decode failed (tuple): {e}")
                continue

        elif isinstance(data_field, dict) and "data" in data_field:
            try:
                inner = data_field["data"]
                if isinstance(inner, (tuple, list)) and len(inner) > 0:
                    raw = base64.b64decode(inner[0])
            except Exception as e:  # pragma: no cover - defensive logging
                print(f"[ERROR] Base64 decode failed (dict): {e}")
                continue

        elif isinstance(data_field, (bytes, bytearray)):
            raw = bytes(data_field)

        else:
            print(f"[WARN] Unknown data format: {type(data_field)} — skipping.")
            continue

        # Filter for valid size
        if not raw or len(raw) < 584:
            continue

        try:
            rd = _parse_round(raw)
            rounds.append(rd)
        except Exception as e:  # pragma: no cover - defensive logging
            print(f"[WARN] Failed to parse round: {e}")
            continue

    print(f"[INFO] Parsed {len(rounds)} round accounts.")
    return rounds


def get_round_snapshot():
    """Return latest ORE round snapshot."""
    rounds = _get_all_round_accounts()
    if not rounds:
        print("[WARN] No round accounts decoded; using dummy data.")
        return {"round_id": 0, "tiles": [{"id": 1, "sol_deployed": 0.1}]}

    # Pick the latest round by id
    latest = max(rounds, key=lambda r: r["id"])

    # Convert lamports -> SOL
    LAMPORTS_PER_SOL = 1_000_000_000
    tiles = [{"id": i + 1, "sol_deployed": latest["deployed"][i] / LAMPORTS_PER_SOL}
             for i in range(25)]

    print(
        f"[ORE] Round #{latest['id']} | "
        f"total_deployed={latest['total_deployed']/LAMPORTS_PER_SOL:.4f} SOL "
        f"| motherlode={latest['motherlode']/LAMPORTS_PER_SOL:.4f} SOL"
    )

    return {
        "round_id": latest["id"],
        "tiles": tiles,
        "motherlode": latest["motherlode"],
        "total_deployed": latest["total_deployed"],
    }


try:
    from solana.transaction import Transaction  # type: ignore
    from solana.system_program import TransferParams, transfer  # type: ignore
    from solders.keypair import Keypair  # type: ignore
except ModuleNotFoundError:
    Transaction = TransferParams = transfer = Keypair = None  # type: ignore[assignment]


def deploy(tile_id, amount_sol):
    """Send a real transaction using your wallet to Ore program."""
    if not _SOLANA_AVAILABLE or client is None or Transaction is None or TransferParams is None:
        raise RuntimeError("Solana SDK is not available. Cannot deploy.")

    try:
        # Load keypair from file
        with open(os.getenv("KEYPAIR_PATH"), "r", encoding="utf-8") as f:
            secret = json.load(f)
        kp = Keypair.from_bytes(bytes(secret))

        # Convert SOL → lamports
        lamports = int(amount_sol * 1_000_000_000)

        # Send to Ore program (placeholder - update this if Ore specifies different destination)
        tx = Transaction().add(
            transfer(
                TransferParams(
                    from_pubkey=kp.pubkey(),
                    to_pubkey=Pubkey.from_string(os.getenv("WALLET_ADDRESS")),
                    lamports=lamports,
                )
            )
        )
        resp = client.send_transaction(tx, kp, opts={"skip_preflight": False})
        print(f"[TX SENT] {resp}")
    except Exception as e:  # pragma: no cover - runtime feedback only
        print(f"[ERROR] Deploy failed: {e}")
