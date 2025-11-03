"""Command-line entry point for the Ore miner simulation."""

import argparse
import time
from typing import Optional

from ore_api import get_round_snapshot, deploy
from strategy import pick_tiles, simulate_profit, init_log, record_profit


def run_loop(dry_run: bool = False, rounds: Optional[int] = None, sleep: float = 5.0) -> None:
    """Run the mining loop.

    Args:
        dry_run: When True, skip on-chain deployments and only log actions.
        rounds: Maximum number of rounds to execute. ``None`` means unlimited.
        sleep: Seconds to wait between rounds.
    """
    print("Starting simulated mining loop...\n")
    init_log()
    total_pnl = 0.0
    round_counter = 1

    while rounds is None or round_counter <= rounds:
        # Fetch current round snapshot
        round_data = get_round_snapshot()
        round_id = round_data.get("round_id", 0)

        # Decide which tiles to deploy
        chosen_tiles = pick_tiles(round_data)

        # Execute (or simulate) deployments
        if dry_run:
            for tile_id in chosen_tiles:
                print(f"[DRY-RUN] Would deploy tile {tile_id} with 0.01 SOL")
        else:
            for tile_id in chosen_tiles:
                deploy(tile_id, 0.01)

        # Simulate profit
        profit = simulate_profit(chosen_tiles)
        total_pnl += profit

        # Log + print
        print(f"[Round {round_counter}] Profit: {profit:.4f} | Total PnL: {total_pnl:.4f}\n")
        record_profit(round_id, chosen_tiles, profit, total_pnl)

        round_counter += 1
        if rounds is not None and round_counter > rounds:
            break

        if sleep > 0:
            time.sleep(sleep)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ore miner simulation runner")
    parser.add_argument("--dry-run", action="store_true", help="Skip real Solana deployments")
    parser.add_argument(
        "--rounds",
        type=int,
        default=0,
        help="Number of rounds to execute (0 for unlimited)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=5.0,
        help="Seconds to sleep between rounds",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    rounds = args.rounds if args.rounds and args.rounds > 0 else None
    sleep = max(args.sleep, 0.0)
    run_loop(dry_run=args.dry_run, rounds=rounds, sleep=sleep)
