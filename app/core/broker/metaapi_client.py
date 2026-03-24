"""
MetaAPI Broker Client — Pure REST API implementation.
Bypasses the MetaAPI SDK WebSocket (which has connection issues) and uses
direct REST API calls via httpx for reliable data fetching and trading.
"""
import asyncio
import time
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, timezone
import httpx

from app.config import settings
from app.utils.logger import logger


# MetaAPI REST API endpoints
PROVISIONING_URL = "https://mt-provisioning-api-v1.agiliumtrade.agiliumtrade.ai"


class MetaAPIClient:
    """REST-based async MetaAPI client."""

    def __init__(self):
        self._connected = False
        self._client: Optional[httpx.AsyncClient] = None
        self._base_url = ""
        self._market_data_url = ""  # Separate hostname for historical candles
        self._headers = {}
        
        # Caching to prevent UI timeouts during heavy background processing
        self._last_account_info = {"balance": 0, "equity": 0, "margin": 0, "free_margin": 0}
        self._last_positions = []
        self._last_account_update = 0
        self._last_positions_update = 0

    async def connect(self) -> bool:
        """Connect to MetaAPI and discover the correct server endpoint."""
        try:
            token = settings.metaapi_token
            account_id = settings.metaapi_account_id

            if not token or not account_id or account_id == "put_your_metaapi_account_id_here":
                logger.error("❌ MetaAPI token or account ID not configured")
                return False

            self._headers = {
                "auth-token": token,
                "Content-Type": "application/json"
            }

            self._client = httpx.AsyncClient(timeout=30, headers=self._headers)

            # Step 1: Get account details from provisioning API to find the region
            logger.info("Fetching account details from MetaAPI...")
            resp = await self._client.get(
                f"{PROVISIONING_URL}/users/current/accounts/{account_id}"
            )

            if resp.status_code != 200:
                logger.error(f"❌ Failed to fetch account: {resp.status_code} {resp.text[:200]}")
                return False

            account_data = resp.json()
            region = account_data.get("region", "london")
            state = account_data.get("state", "UNKNOWN")
            connection_status = account_data.get("connectionStatus", "UNKNOWN")

            logger.info(f"  Account: {account_data.get('name', 'N/A')}")
            logger.info(f"  Region: {region}, State: {state}, Connection: {connection_status}")

            # Step 2: Deploy if needed
            if state != "DEPLOYED":
                logger.info("Deploying account...")
                deploy_resp = await self._client.post(
                    f"{PROVISIONING_URL}/users/current/accounts/{account_id}/deploy"
                )
                if deploy_resp.status_code not in (200, 204):
                    logger.error(f"❌ Deploy failed: {deploy_resp.text[:200]}")
                    return False

                # Wait for deployment
                for _ in range(30):
                    await asyncio.sleep(2)
                    check = await self._client.get(
                        f"{PROVISIONING_URL}/users/current/accounts/{account_id}"
                    )
                    if check.status_code == 200 and check.json().get("state") == "DEPLOYED":
                        break
                else:
                    logger.error("❌ Account deployment timed out")
                    return False

            # Set the client API base URL based on region
            # MetaAPI uses regional servers like london-b, new-york-a, etc.
            self._base_url = f"https://mt-client-api-v1.{region}-b.agiliumtrade.ai"
            # Historical candle data is on a DIFFERENT hostname per MetaAPI docs
            self._market_data_url = f"https://mt-market-data-client-api-v1.{region}.agiliumtrade.ai"

            # Step 3: Verify connection with a simple price check (with retries)
            logger.info(f"Testing connection to {self._base_url}...")
            for attempt in range(3):
                try:
                    test_resp = await self._client.get(
                        f"{self._base_url}/users/current/accounts/{account_id}/symbols/EURUSD/current-price"
                    )
                    if test_resp.status_code == 200:
                        price = test_resp.json()
                        logger.info(f"  ✅ Connection verified! EURUSD: {price.get('bid')}/{price.get('ask')}")
                        self._connected = True
                        return True
                    elif test_resp.status_code == 504:
                        logger.warning(f"  Attempt {attempt+1}/3: Server timeout, retrying...")
                        await asyncio.sleep(5)
                    else:
                        logger.warning(f"  Attempt {attempt+1}/3: {test_resp.status_code}")
                        await asyncio.sleep(3)
                except Exception as e:
                    logger.warning(f"  Attempt {attempt+1}/3 error: {e}")
                    await asyncio.sleep(3)

            # Even if price check fails, mark as connected if account is deployed
            logger.warning("Price check failed, but account is deployed. Marking as connected.")
            self._connected = True
            return True

        except Exception as e:
            logger.error(f"❌ MetaAPI connection failed: {e}")
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def _account_url(self) -> str:
        return f"{self._base_url}/users/current/accounts/{settings.metaapi_account_id}"

    async def _get(self, path: str, params: dict = None) -> Optional[dict]:
        """Make a GET request with error handling and retry."""
        if not self._client:
            return None
        url = f"{self._account_url}{path}"
        for attempt in range(2):
            try:
                resp = await self._client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 504:
                    logger.debug(f"Timeout on {path}, retrying...")
                    await asyncio.sleep(3)
                else:
                    logger.warning(f"API {path} returned {resp.status_code}: {resp.text[:200]}")
                    return None
            except Exception as e:
                logger.warning(f"API {path} error: {e}")
                await asyncio.sleep(2)
        return None

    async def _post(self, path: str, json_data: dict = None) -> Optional[dict]:
        """Make a POST request with error handling."""
        if not self._client:
            return None
        url = f"{self._account_url}{path}"
        try:
            resp = await self._client.post(url, json=json_data)
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                logger.warning(f"API POST {path} returned {resp.status_code}: {resp.text[:200]}")
                return {"error": resp.text[:200]}
        except Exception as e:
            logger.error(f"API POST {path} error: {e}")
            return {"error": str(e)}

    async def get_account_info(self, use_cache: bool = False) -> Dict[str, Any]:
        """Get account balance, equity, margin info. Uses cache on timeout or explicitly."""
        if not self._connected:
            return {"error": "Not connected"}
            
        if use_cache:
            if self._last_account_update > 0:
                return self._last_account_info
            return {"error": "Waiting for initial sync from broker...", "balance": 0, "equity": 0}

        data = await self._get("/account-information")
        if data and "error" not in data:
            self._last_account_info = {
                "balance": data.get("balance", 0),
                "equity": data.get("equity", 0),
                "margin": data.get("margin", 0),
                "free_margin": data.get("freeMargin", 0),
                "leverage": data.get("leverage", 0),
                "currency": data.get("currency", "USD"),
                "server": data.get("server", ""),
                "platform": data.get("platform", "mt5"),
            }
            self._last_account_update = time.time()
            return self._last_account_info
            
        if self._last_account_update > 0:
            logger.debug("Returning cached account info due to API timeout")
            return self._last_account_info
            
        return {"error": "Failed to fetch account info", "balance": 0, "equity": 0}

    async def get_positions(self, use_cache: bool = False) -> List[Dict[str, Any]]:
        """Get all open positions. Uses cache on timeout or explicitly."""
        if not self._connected:
            return []
            
        if use_cache:
            if self._last_positions_update > 0:
                return self._last_positions
            return []

        data = await self._get("/positions")
        if data is None:
            if self._last_positions_update > 0:
                return self._last_positions
            return []

        if isinstance(data, list):
            self._last_positions = [
                {
                    "id": p.get("id", ""),
                    "symbol": p.get("symbol", ""),
                    "type": p.get("type", ""),
                    "volume": p.get("volume", 0),
                    "open_price": p.get("openPrice", 0),
                    "current_price": p.get("currentPrice", 0),
                    "profit": p.get("profit", 0),
                    "swap": p.get("swap", 0),
                    "stop_loss": p.get("stopLoss"),
                    "take_profit": p.get("takeProfit"),
                    "open_time": p.get("time", ""),
                }
                for p in data
            ]
            self._last_positions_update = time.time()
            return self._last_positions
        return []

    async def get_candles(
        self, symbol: str, timeframe: str = "1h", count: int = 100
    ) -> List[Dict[str, Any]]:
        """Get historical OHLCV candle data via REST API.
        Note: MetaAPI hosts candle data on a SEPARATE hostname from the main API.
        """
        if not self._connected or not self._client:
            return []

        # Candles are on the market-data hostname, not the regular client API
        market_data_account_url = f"{self._market_data_url}/users/current/accounts/{settings.metaapi_account_id}"
        url = f"{market_data_account_url}/historical-market-data/symbols/{symbol}/timeframes/{timeframe}/candles"

        for attempt in range(2):
            try:
                resp = await self._client.get(url, params={"limit": count})
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        return [
                            {
                                "time": c.get("time", ""),
                                "open": c.get("open", 0),
                                "high": c.get("high", 0),
                                "low": c.get("low", 0),
                                "close": c.get("close", 0),
                                "volume": c.get("tickVolume", c.get("volume", 0)),
                            }
                            for c in data
                        ]
                    return []
                elif resp.status_code == 504:
                    logger.debug(f"Candle timeout for {symbol}/{timeframe}, retrying...")
                    await asyncio.sleep(3)
                else:
                    logger.warning(f"Candle API {symbol}/{timeframe} returned {resp.status_code}: {resp.text[:200]}")
                    return []
            except Exception as e:
                logger.warning(f"Candle fetch error {symbol}/{timeframe}: {e}")
                await asyncio.sleep(2)
        return []

    async def get_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current bid/ask price."""
        if not self._connected:
            return None

        data = await self._get(f"/symbols/{symbol}/current-price")
        if data:
            bid = data.get("bid", 0)
            ask = data.get("ask", 0)
            return {
                "bid": bid,
                "ask": ask,
                "spread": ask - bid,
            }
        return None

    async def place_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "ForeksTrader",
    ) -> Dict[str, Any]:
        """Place a market order (BUY or SELL)."""
        if not self._connected:
            return {"error": "Not connected"}

        action_type = "ORDER_TYPE_BUY" if direction.upper() == "BUY" else "ORDER_TYPE_SELL"

        order_data = {
            "actionType": action_type,
            "symbol": symbol,
            "volume": volume,
            "comment": comment,
        }

        if stop_loss is not None:
            order_data["stopLoss"] = stop_loss
        if take_profit is not None:
            order_data["takeProfit"] = take_profit

        result = await self._post("/trade", json_data=order_data)

        if result and "error" not in result:
            logger.info(f"📊 Order placed: {direction} {volume} {symbol}")
            return {
                "success": True,
                "order_id": result.get("orderId", ""),
                "position_id": result.get("positionId", ""),
            }
        else:
            error_msg = result.get("error", "Unknown error") if result else "No response"
            logger.error(f"❌ Order failed: {error_msg}")
            return {"error": error_msg}

    async def close_position(self, position_id: str) -> Dict[str, Any]:
        """Close a specific position."""
        if not self._connected:
            return {"error": "Not connected"}

        result = await self._post("/trade", json_data={
            "actionType": "POSITION_CLOSE_ID",
            "positionId": position_id,
        })

        if result and "error" not in result:
            logger.info(f"📊 Position closed: {position_id}")
            return {"success": True, "result": result}
        return {"error": result.get("error", "Unknown") if result else "No response"}

    async def modify_position(
        self, position_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict[str, Any]:
        """Modify stop loss / take profit of an open position."""
        if not self._connected:
            return {"error": "Not connected"}

        modify_data = {
            "actionType": "POSITION_MODIFY",
            "positionId": position_id,
        }
        if stop_loss is not None:
            modify_data["stopLoss"] = stop_loss
        if take_profit is not None:
            modify_data["takeProfit"] = take_profit

        result = await self._post("/trade", json_data=modify_data)
        if result and "error" not in result:
            return {"success": True, "result": result}
        return {"error": result.get("error", "Unknown") if result else "No response"}

    async def get_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get closed trade history."""
        if not self._connected:
            return []
        start = datetime.now(timezone.utc) - timedelta(days=days)
        data = await self._get(
            "/history-deals/time",
            params={
                "startTime": start.isoformat(),
                "endTime": datetime.now(timezone.utc).isoformat()
            }
        )
        if data and isinstance(data, list):
            return [
                {
                    "id": d.get("id", ""),
                    "position_id": d.get("positionId", ""),
                    "symbol": d.get("symbol", ""),
                    "type": d.get("type", ""),
                    "volume": d.get("volume", 0),
                    "price": d.get("price", 0),
                    "profit": d.get("profit", 0),
                    "commission": d.get("commission", 0),
                    "swap": d.get("swap", 0),
                    "time": d.get("time", ""),
                }
                for d in data
            ]
        return []

    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """Get symbol specification (digits, lot size, etc.)."""
        if not self._connected:
            return {}

        data = await self._get(f"/symbols/{symbol}/specification")
        if data:
            return {
                "symbol": symbol,
                "digits": data.get("digits", 5),
                "contract_size": data.get("contractSize", 100000),
                "min_volume": data.get("minVolume", 0.01),
                "max_volume": data.get("maxVolume", 100),
                "volume_step": data.get("volumeStep", 0.01),
                "point": data.get("point", 0.00001),
            }
        return {
            "symbol": symbol, "digits": 5, "contract_size": 100000,
            "min_volume": 0.01, "max_volume": 100, "volume_step": 0.01, "point": 0.00001
        }

    async def disconnect(self):
        """Gracefully close the HTTP client."""
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass
        self._connected = False
        logger.info("Disconnected from MetaAPI")


# Singleton instance
broker = MetaAPIClient()
