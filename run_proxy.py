#https://github.com/z0zero || @z0zero
import aiohttp
import asyncio
import json
import uuid
import time
from loguru import logger
import requests
from aiohttp import ClientSession, ClientTimeout
from fake_useragent import UserAgent
import itertools
import sys
import random

# Function to read proxies from the local file
def load_proxies(file_path='local_proxies.txt'):
    with open(file_path, 'r') as f:
        proxies = [line.strip() for line in f.readlines()]
    return proxies  # Return all proxies if there are 100 or more

# Function to get the UID using the provided token
def get_uid(token):
    try:
        url = "https://api.aigaea.net/api/auth/session"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Origin": "https://app.aigaea.net",
            "Referer": "https://app.aigaea.net/",
            "Sec-Ch-Ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        
        payload = {
            "token": token
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            logger.error(f"Failed to get UID. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            if response.status_code == 500:
                logger.info("Retrying after 5 seconds...")
                time.sleep(5)
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    uid = result.get('data', {}).get('uid')
                    if uid:
                        logger.success(f"Successfully got UID on retry: {uid}")
                        return uid
            return None
            
        result = response.json()
        uid = result.get('data', {}).get('uid')
        if not uid:
            logger.error(f"UID not found in response: {result}")
            return None
            
        logger.success(f"Successfully got UID: {uid}")
        return uid
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while getting UID: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error while getting UID: {str(e)}")
        return None

# Function to connect to the API using a proxy from the list
async def connect_to_http(uid, token, proxy, device_id):
    random_delay = random.uniform(1, 5)
    await asyncio.sleep(random_delay)
    
    user_agent = random.choice(COMMON_BROWSERS)
    logger.info(f"Using proxy: {proxy} after {random_delay:.2f}s delay")

    async with aiohttp.ClientSession(
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": user_agent, "Connection": "keep-alive"},
        timeout=ClientTimeout(total=None, connect=10),
    ) as session:
        try:
            uri = "https://api.aigaea.net/api/network/ping"
            logger.info(f"Browser Id : {device_id}")
            logger.info(f"Connecting to {uri} using proxy: {proxy}...")

            timestamp_jitter = int(time.time()) + random.randint(-2, 2)
            
            data = {
                "uid": uid,
                "browser_id": device_id,
                "timestamp": timestamp_jitter,
                "version": "1.0.0",
            }

            async with session.post(uri, json=data, proxy=f"{proxy}") as response:
                if response.status == 200:
                    response_data = await response.json()
                    logger.success(f"Success: Proxy {proxy} - Response: {response_data}")
                elif response.status == 429:
                    logger.warning(f"Rate limited for proxy {proxy}. Waiting longer...")
                    await asyncio.sleep(random.uniform(10, 15))
                else:
                    logger.error(f"Request failed with status {response.status} for proxy {proxy}")
                    await asyncio.sleep(random.uniform(3, 5))
        except aiohttp.ClientProxyConnectionError:
            logger.error(f"Proxy connection failed: {proxy}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout for proxy: {proxy}")
        except Exception as e:
            logger.error(f"Unexpected error with proxy {proxy}: {str(e)}")

# Function to run all proxies concurrently
async def run_all_proxies(uid, token, proxies, device_ids):
    tasks = []
    
    # Create a task for each proxy using its dedicated device_id
    for proxy, device_id in zip(proxies, device_ids):
        task = asyncio.create_task(connect_to_http(uid, token, proxy, device_id))
        tasks.append(task)
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)

# Function to loop through proxies continuously
async def loop_proxies(uid, token, proxies, base_delay, loop_count=None):
    stats = {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0
    }
    
    device_ids = [str(uuid.uuid4()) for _ in proxies]
    count = 0
    retry_counts = {proxy: 0 for proxy in proxies}
    MAX_RETRIES = 3
    
    while True:
        active_proxies = [p for p in proxies if retry_counts[p] < MAX_RETRIES]
        
        stats["total_requests"] += len(active_proxies)
        logger.info(f"Statistics: {stats}")
        
        logger.info(f"Starting loop {count + 1}...")
        
        if not active_proxies:
            logger.error("All proxies have exceeded retry limit. Exiting...")
            break
            
        active_device_ids = [d for p, d in zip(proxies, device_ids) if p in active_proxies]
        await run_all_proxies(uid, token, active_proxies, active_device_ids)
        
        random_delay = base_delay + random.uniform(-5, 5)
        print(f"Cycle {count + 1} completed. Waiting {random_delay:.2f} seconds before next cycle...")
        await asyncio.sleep(random_delay)
        
        count += 1
        if loop_count and count >= loop_count:
            logger.info(f"Completed {loop_count} loops. Exiting.")
            break

# For testing the function
async def main():
    try:
        base_delay = int(input('Input Base Delay Second Per Looping : '))
        tokenid = input('Input Token AIGAEA : ')
        
        if base_delay < 10:
            logger.warning("Base delay terlalu rendah, disarankan minimal 10 detik")
            return
            
        proxies = load_proxies()
        if not proxies:
            logger.error("Tidak ada proxy yang tersedia")
            return
            
        logger.info(f"Starting bot with {len(proxies)} proxies")
        
        # Dapatkan UID dan validasi
        uid = get_uid(tokenid)
        if not uid:
            logger.error("Gagal mendapatkan UID. Mohon periksa token Anda.")
            return
            
        await loop_proxies(uid, tokenid, proxies, base_delay)
    except KeyboardInterrupt:
        logger.info("Bot dihentikan oleh user")
    except Exception as e:
        logger.error(f"Error tidak terduga: {str(e)}")
    finally:
        logger.info("Bot berhenti")

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())