import argparse
import logging
import signal
import sys
from time import sleep

from prometheus_client import Gauge, start_http_server
from requests import get

logger = logging.getLogger()

cli = argparse.ArgumentParser(description="yieldwatch Prometheus Exporter")
cli.add_argument("--wallet", metavar="wallet id", type=str,
                 help="Wallet direction")
cli.add_argument("--port", metavar="server port", type=int,
                 help="Port", default=18765)
cli.add_argument("--debug", action="store_true")

gBalancce = Gauge("balance", "Current Balance", [
                  "vault", "token", "priceinusd", "wallet"])
gDeposit = Gauge("deposit", "Current Deposit", [
                 "vault", "token", "priceinusd", "wallet"])
gPendingReward = Gauge("pending_reward", "Current Reward", [
                       "vault", "token", "priceinusd", "wallet"])
gHarvested = Gauge("harvested_reward", "Current Reward", [
                   "vault", "token", "priceinusd", "wallet"])
gPendingRewardUSD = Gauge("pending_reward_usd", "Current Reward", [
                          "vault", "token", "priceinusd", "wallet"])
gHarvestedUSD = Gauge("harvested_reward_usd", "Current Reward", [
                      "vault", "token", "priceinusd", "wallet"])


def containsVaultInformation(farm):
    return farm.get("vaults", None) is not None and farm["vaults"].get("vaults", None) is not None


def query(wallet):
    # Currently only supports vault. No staking supported yet
    params = {
        "platforms": "beefy,pancake,hyperjump,blizzard,bdollar,jetfuel,auto,bunny,acryptos,alpha,venus,cream"
    }
    response = get(
        f"https://www.yieldwatch.net/api/all/{wallet}", params=params)
    if response.json()["message"] == "OK" and response.json()["status"] == "1":
        ratelimit = response.headers["x-ratelimit-remaining"]
        logger.debug(f"Remaining ratelimit: {ratelimit}")
        result = response.json()["result"]
        vaultFarms = [result[farm_name]
                      for farm_name in result if containsVaultInformation(result[farm_name])]
        for farm in vaultFarms:
            processVault(farm)
    else:
        logger.warn("Yieldwatch failed")
        logger.warn(
            f"Yieldwatch response {response.status_code}: {response.text}")


def processVault(farm):
    logger.debug(f"Processing: {farm}")
    for vault in farm["vaults"]["vaults"]:
        logger.debug(f"Processing: {vault}")
        logger.debug(f"Vault name: {vault['name']}")
        logger.debug(f"Balance: {vault['currentTokens']}")
        logger.debug(f"Deposit: {vault['depositedTokens']}")

        gBalancce.labels(vault["name"], vault["depositToken"], vault["priceInUSDDepositToken"], wallet).set(
            vault["currentTokens"])
        gDeposit.labels(vault["name"], vault["depositToken"], vault["priceInUSDDepositToken"], wallet).set(
            vault["depositedTokens"])
        gPendingReward.labels(vault["name"], vault["rewardToken"], vault["priceInUSDRewardToken"], wallet).set(
            vault["pendingRewards"])
        gHarvested.labels(vault["name"], vault["rewardToken"], vault["priceInUSDRewardToken"], wallet).set(
            vault["harvestedRewards"])
        gPendingRewardUSD.labels(vault["name"], vault["rewardToken"], vault["priceInUSDRewardToken"], wallet).set(
            vault["pendingRewards"] * vault["priceInUSDRewardToken"])
        gHarvestedUSD.labels(vault["name"], vault["rewardToken"], vault["priceInUSDRewardToken"], wallet).set(
            vault["harvestedRewards"] * vault["priceInUSDRewardToken"])


def signal_handler(sig, frame):
    print("Stopping")
    sys.exit(0)


if __name__ == '__main__':
    # CLI Parsing
    args = cli.parse_args()
    wallet = args.wallet
    port = args.port

    # Configuring logging
    logger.setLevel(level=logging.INFO)
    if args.debug:
        logger.setLevel(level=logging.DEBUG)
    stout = logging.StreamHandler(sys.stdout)
    stout.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(stout)

    # Starting the service
    logger.info(f"Starting the server in the {port}")
    logger.info("Press Ctrl+C to stop the exporter")
    start_http_server(port)
    signal.signal(signal.SIGINT, signal_handler)

    # Software loop
    while True:
        query(wallet)
        logger.debug("Waiting 5 seconds to avoid yieldwatch rate limit")
        sleep(5)
    signal.pause()
