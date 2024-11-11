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

# Function to get the UID menggunakan token yang diberikan dengan mekanisme retry
def get_uid(token, max_retries=5, backoff_factor=2):
    try:
        url = "https://api.aigaea.net/api/auth/session"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Origin": "http://app.aigaea.net",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, seperti Gecko) Chrome/109.0.0.0 Safari/537.36"
        }

        attempt = 0
        while attempt < max_retries:
            response = requests.post(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                uid = result.get('data', {}).get('uid')
                if uid:
                    logger.success(f"Berhasil mendapatkan UID: {uid}")
                    return uid
                else:
                    logger.error(f"UID tidak ditemukan dalam respons: {result}")
                    return None
            elif response.status_code == 500:
                attempt += 1
                sleep_time = backoff_factor ** attempt
                logger.error(f"Kesalahan server (500). Mencoba ulang {attempt}/{max_retries} setelah {sleep_time} detik...")
                time.sleep(sleep_time)
            else:
                logger.error(f"Gagal mendapatkan UID. Status code: {response.status_code}")
                logger.error(f"Respons: {response.text}")
                return None

        logger.error("Mencapai batas maksimal percobaan ulang. Gagal mendapatkan UID.")
        return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Kesalahan jaringan saat mendapatkan UID: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Kesalahan tidak terduga saat mendapatkan UID: {str(e)}")
        return None

# Function to connect to the API menggunakan proxy dari daftar
async def connect_to_http(uid, token, proxy, device_id):
    try:
        user_agent = UserAgent(os=['windows', 'macos', 'linux'], browsers=['chrome'])
        random_user_agent = user_agent.random
    except Exception as e:
        logger.error(f"Gagal mendapatkan User-Agent: {str(e)}")
        random_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, seperti Gecko) Chrome/109.0.0.0 Safari/537.36"

    random_delay = random.uniform(1, 5)
    await asyncio.sleep(random_delay)
    
    logger.info(f"Menggunakan proxy: {proxy} setelah jeda {random_delay:.2f}s")
    
    async with aiohttp.ClientSession(
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": random_user_agent,
            "Connection": "keep-alive"
        },
        timeout=ClientTimeout(total=None, connect=10),
    ) as session:
        try:
            uri = "https://api.aigaea.net/api/network/ping"
            logger.info(f"Browser Id : {device_id}")
            logger.info(f"Menghubungkan ke {uri} menggunakan proxy: {proxy}...")

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
                    logger.success(f"Berhasil: Proxy {proxy} - Respons: {response_data}")
                elif response.status == 429:
                    logger.warning(f"Dibatasi rate untuk proxy {proxy}. Menunggu lebih lama...")
                    await asyncio.sleep(random.uniform(10, 15))
                else:
                    logger.error(f"Permintaan gagal dengan status {response.status} untuk proxy {proxy}")
                    await asyncio.sleep(random.uniform(3, 5))
        except aiohttp.ClientProxyConnectionError:
            logger.error(f"Koneksi proxy gagal: {proxy}")
        except asyncio.TimeoutError:
            logger.error(f"Waktu habis untuk proxy: {proxy}")
        except Exception as e:
            logger.error(f"Kesalahan tidak terduga dengan proxy {proxy}: {str(e)}")

# Function to run all proxies secara bersamaan
async def run_all_proxies(uid, token, proxies):
    tasks = []
    device_id = str(uuid.uuid4())
    
    # Membuat tugas untuk setiap proxy
    for proxy in proxies:
        task = asyncio.create_task(connect_to_http(uid, token, proxy, device_id))
        tasks.append(task)
    
    # Menjalankan semua tugas secara bersamaan
    await asyncio.gather(*tasks, return_exceptions=True)

# Function to loop through proxies secara terus-menerus
async def loop_proxies(uid, token, proxies, delays, loop_count=None):
    count = 0
    while True:
        logger.info(f"Memulai loop {count + 1}...")
        await run_all_proxies(uid, token, proxies)
        
        # Menambahkan jeda antara setiap siklus
        print(f"Cycle {count + 1} selesai. Menunggu sebelum loop berikutnya dalam {delays} detik...")
        await asyncio.sleep(delays)  # Delay antara siklus (dalam detik)
        
        # Increment loop counter dan periksa apakah harus berhenti setelah iterasi tertentu
        count += 1
        if loop_count and count >= loop_count:
            logger.info(f"Selesai {loop_count} loops. Keluar.")
            break

# For testing the function
async def main():
    try:
        delays = int(input('Input Delay Second Per Looping : '))
        tokenid = input('Input Token AIGAEA : ')
        proxies = load_proxies()  # Load proxies dari file lokal
        loop_count = None  # Set jumlah loop tertentu, atau None untuk looping tak terbatas
        await loop_proxies(get_uid(tokenid), tokenid, proxies, delays, loop_count)
    except KeyboardInterrupt:
        logger.info("Bot dihentikan oleh user")
    except Exception as e:
        logger.error(f"Kesalahan tidak terduga: {str(e)}")
    finally:
        logger.info("Bot berhenti")

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())