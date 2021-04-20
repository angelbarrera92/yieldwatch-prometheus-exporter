import argparse
import logging
import signal
import sys
from time import sleep

from prometheus_client import Counter, Gauge, start_http_server
from requests import get

logger = logging.getLogger()

cli = argparse.ArgumentParser(description="yieldwatch Prometheus Exporter")
cli.add_argument("--wallet", metavar="wallet id", type=str,
                 help="Wallet direction")
cli.add_argument("--port", metavar="server port", type=int,
                 help="Port", default=18765)
cli.add_argument("--debug", action="store_true")

gBalance = Gauge("balance", "Current Balance (tokens)", [
    "vault", "token", "wallet"])
gBalanceUSD = Gauge("balance_usd", "Current Balance in USD", [
    "vault", "token", "wallet"])

gDeposit = Gauge("deposit", "Current Deposit", [
                 "vault", "token", "wallet"])
gDepositUSD = Gauge("deposit_usd", "Current Deposit", [
    "vault", "token", "wallet"])

gPendingReward = Gauge("pending_reward", "Current Reward", [
                       "vault", "token", "wallet"])
gPendingRewardUSD = Gauge("pending_reward_usd", "Current Reward", [
                          "vault", "token", "wallet"])

gHarvested = Gauge("harvested_reward", "Current Reward", [
                   "vault", "token", "wallet"])
gHarvestedUSD = Gauge("harvested_reward_usd", "Current Reward", [
                      "vault", "token", "wallet"])
apy = Gauge("apy", "annual_percentage_yield", ["vault", "wallet"])
reward_token_price = Gauge(
    "reward_token_price", "reward_token_price", ["token"])
deposit_token_price = Gauge("deposit_token_price",
                            "deposit_token_price", ["token"])
err = Counter("yieldwatch_errors", "YieldWatch API Errors")


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
        err.inc()


def processVault(farm):
    logger.debug(f"Processing: {farm}")
    for vault in farm["vaults"]["vaults"]:
        logger.debug(f"Processing: {vault}")
        logger.debug(f"Vault name: {vault['name']}")
        logger.debug(f"Balance: {vault['currentTokens']}")
        logger.debug(f"Deposit: {vault['depositedTokens']}")

        gBalance.labels(vault["name"], vault["depositToken"], wallet).set(
            vault["currentTokens"])
        gBalanceUSD.labels(vault["name"], vault["depositToken"], wallet).set(
            vault["currentTokens"] * vault["priceInUSDDepositToken"])
        gDeposit.labels(vault["name"], vault["depositToken"], wallet).set(
            vault["depositedTokens"])
        gDepositUSD.labels(vault["name"], vault["depositToken"], wallet).set(
            vault["depositedTokens"] * vault["priceInUSDDepositToken"])
        gPendingReward.labels(vault["name"], vault["rewardToken"], wallet).set(
            vault["pendingRewards"])
        gHarvested.labels(vault["name"], vault["rewardToken"], wallet).set(
            vault["harvestedRewards"])
        gPendingRewardUSD.labels(vault["name"], vault["rewardToken"], wallet).set(
            vault["pendingRewards"] * vault["priceInUSDRewardToken"])
        gHarvestedUSD.labels(vault["name"], vault["rewardToken"], wallet).set(
            vault["harvestedRewards"] * vault["priceInUSDRewardToken"])
        apy.labels(vault["name"], wallet).set(vault["apy"])
        reward_token_price.labels(vault["rewardToken"]).set(
            vault["priceInUSDRewardToken"])
        deposit_token_price.labels(vault["depositToken"]).set(
            vault["priceInUSDDepositToken"])


def signal_handler(sig, frame):
    print("Stopping")
    sys.exit(0)


if __name__ == "__main__":
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
