
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
    "vault", "token", "wallet", "farm"])
gBalanceUSD = Gauge("balance_usd", "Current Balance in USD", [
    "vault", "token", "wallet", "farm"])

gDeposit = Gauge("deposit", "Current Deposit", [
                 "vault", "token", "wallet", "farm"])
gDepositUSD = Gauge("deposit_usd", "Current Deposit", [
    "vault", "token", "wallet", "farm"])

gPendingReward = Gauge("pending_reward", "Current Reward", [
                       "vault", "token", "wallet", "farm"])
gPendingRewardUSD = Gauge("pending_reward_usd", "Current Reward", [
                          "vault", "token", "wallet", "farm"])

gHarvested = Gauge("harvested_reward", "Current Reward", [
                   "vault", "token", "wallet", "farm"])
gHarvestedUSD = Gauge("harvested_reward_usd", "Current Reward", [
                      "vault", "token", "wallet", "farm"])
apy = Gauge("apy", "annual_percentage_yield", ["vault", "wallet", "farm"])
reward_token_price = Gauge(
    "reward_token_price", "reward_token_price", ["token", "vault", "farm"])
deposit_token_price = Gauge("deposit_token_price",
                            "deposit_token_price", ["token", "vault", "farm"])
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
        vaultFarms = [farm_name
                      for farm_name in result if containsVaultInformation(result[farm_name])]
        for farm_name in vaultFarms:
            processVault(farm_name, result[farm_name])
    else:
        logger.warn("Yieldwatch failed")
        logger.warn(
            f"Yieldwatch response {response.status_code}: {response.text}")
        err.inc()


def processVault(farm_name, farm):
    logger.debug(f"Processing: {farm} @ {farm_name}")
    for vault in farm["vaults"]["vaults"]:
        logger.debug(f"Processing: {vault}")
        logger.debug(f"Vault name: {vault['name']}")
        logger.debug(f"Balance: {vault['currentTokens']}")
        logger.debug(f"Deposit: {vault['depositedTokens']}")

        gBalance.labels(vault["name"], vault["depositToken"], wallet, farm_name).set(
            vault["currentTokens"])
        gBalanceUSD.labels(vault["name"], vault["depositToken"], wallet, farm_name).set(
            vault["currentTokens"] * vault["priceInUSDDepositToken"])
        gDeposit.labels(vault["name"], vault["depositToken"], wallet, farm_name).set(
            vault["depositedTokens"])
        gDepositUSD.labels(vault["name"], vault["depositToken"], wallet, farm_name).set(
            vault["depositedTokens"] * vault["priceInUSDDepositToken"])
        gPendingReward.labels(vault["name"], vault["rewardToken"], wallet, farm_name).set(
            vault["pendingRewards"])

        if "harvestedRewards" in vault:
            gHarvested.labels(vault["name"], vault["rewardToken"], wallet, farm_name).set(
                vault["harvestedRewards"])
            gHarvestedUSD.labels(vault["name"], vault["rewardToken"], wallet, farm_name).set(
                vault["harvestedRewards"] * vault["priceInUSDRewardToken"])

        gPendingRewardUSD.labels(vault["name"], vault["rewardToken"], wallet, farm_name).set(
            vault["pendingRewards"] * vault["priceInUSDRewardToken"])
        apy.labels(vault["name"], wallet, farm_name).set(vault["apy"])
        reward_token_price.labels(vault["rewardToken"], vault["name"], farm_name).set(
            vault["priceInUSDRewardToken"])
        deposit_token_price.labels(vault["depositToken"], vault["name"], farm_name).set(
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
