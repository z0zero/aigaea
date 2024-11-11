#https://github.com/z0zero || @z0zero
import os
import requests
import uuid
import time
import threading
import logging
import socket
import socks
from typing import List
from requests.exceptions import RequestException

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProxyFormat:
    def __init__(self, proxy_string: str):
        """
        Parse proxy string in format: scheme://ip:port@username:password
        """
        try:
            # Split scheme if exists
            if "://" in proxy_string:
                self.scheme, remainder = proxy_string.split("://", 1)
            else:
                self.scheme = "http"
                remainder = proxy_string
            
            # Split address and auth
            if "@" in remainder:
                address, auth = remainder.split("@", 1)
                self.ip, self.port = address.split(":", 1)
                self.username, self.password = auth.split(":", 1)
            else:
                self.ip, self.port = remainder.split(":", 1)
                self.username = self.password = None
            
            # Convert port to integer
            self.port = int(self.port)
                
        except Exception as e:
            raise ValueError(f"Invalid proxy format: {proxy_string}") from e

class AigaeaPinger:
    def __init__(self, token: str, user_uid: str, proxy_file: str):
        self.token = token
        self.user_uid = user_uid
        self.proxy_file = proxy_file
        self.running = False
        self.threads = []
        
        self.headers = {
            "authorization": f"Bearer {self.token}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
            "accept": "application/json",
            "content-type": "application/json",
            "origin": "https://app.aigaea.net",
            "referer": "https://app.aigaea.net/",
            "accept-language": "en-US,en;q=0.9",
            "priority": "u=1, i"
        }

    def _load_proxies(self) -> List[str]:
        try:
            with open(self.proxy_file, 'r') as f:
                return [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except Exception as e:
            logger.error(f"Error loading proxy file: {str(e)}")
            return []

    def _setup_socks_session(self, proxy: ProxyFormat) -> requests.Session:
        """Create a session with SOCKS proxy configuration"""
        session = requests.Session()
        
        if proxy.scheme.lower() in ['socks5', 'socks4']:
            # Determine SOCKS version
            socks_version = socks.SOCKS5 if proxy.scheme.lower() == 'socks5' else socks.SOCKS4
            
            # Configure the SOCKS proxy
            session.proxies = {
                'http': f'{proxy.scheme}://{proxy.ip}:{proxy.port}',
                'https': f'{proxy.scheme}://{proxy.ip}:{proxy.port}'
            }
            
            if proxy.username and proxy.password:
                session.proxies = {
                    'http': f'{proxy.scheme}://{proxy.username}:{proxy.password}@{proxy.ip}:{proxy.port}',
                    'https': f'{proxy.scheme}://{proxy.username}:{proxy.password}@{proxy.ip}:{proxy.port}'
                }
            
            # Optional: Set up SOCKS proxy without altering global socket
            session.trust_env = False  # Avoid inheriting proxies from environment
        return session

    def _worker(self, proxy_string: str):
        try:
            proxy = ProxyFormat(proxy_string)
            session = self._setup_socks_session(proxy) if proxy.scheme.lower() in ['socks5', 'socks4'] else requests.Session()
            
            browser_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, proxy_string))
            
            while self.running:
                try:
                    payload = {
                        "uid": self.user_uid,
                        "browser_id": browser_id,
                        "timestamp": int(time.time()),
                        "version": "1.0.0"
                    }
                    
                    if proxy.scheme.lower() in ['socks5', 'socks4']:
                        response = session.post(
                            url="https://api.aigaea.net/api/network/ping",
                            json=payload,
                            headers=self.headers,
                            timeout=30,
                            verify=True
                        )
                    else:
                        proxies = {
                            "http": f"{proxy.scheme}://{proxy.username}:{proxy.password}@{proxy.ip}:{proxy.port}",
                            "https": f"{proxy.scheme}://{proxy.username}:{proxy.password}@{proxy.ip}:{proxy.port}"
                        } if proxy.username and proxy.password else {
                            "http": f"{proxy.scheme}://{proxy.ip}:{proxy.port}",
                            "https": f"{proxy.scheme}://{proxy.ip}:{proxy.port}"
                        }
                        
                        response = session.post(
                            url="https://api.aigaea.net/api/network/ping",
                            json=payload,
                            headers=self.headers,
                            proxies=proxies,
                            timeout=30,
                            verify=True
                        )
                    
                    if response.status_code == 200:
                        data = response.json()
                        logger.info(f"Success - Proxy: {proxy_string} - Response: {data}")
                        sleep_time = data.get("data", {}).get("interval", 60)
                        logger.info(f"Sleeping for {sleep_time} seconds")
                        time.sleep(int(sleep_time))
                    else:
                        logger.error(f"Error - Proxy: {proxy_string} - Status Code: {response.status_code}")
                        time.sleep(60)
                        
                except RequestException as e:
                    logger.error(f"Request Error - Proxy: {proxy_string} - Error: {str(e)}")
                    time.sleep(60)
                    
                except Exception as e:
                    logger.error(f"General Error - Proxy: {proxy_string} - Error: {str(e)}")
                    time.sleep(60)
                    
        except ValueError as ve:
            logger.error(f"Worker Initialization Error - Proxy: {proxy_string} - Error: {str(ve)}")
        except Exception as e:
            logger.error(f"Worker Error - Proxy: {proxy_string} - Error: {str(e)}")

    def start(self):
        self.running = True
        
        proxies = self._load_proxies()
        if not proxies:
            logger.error("No valid proxies found in file")
            return
            
        for proxy in proxies:
            thread = threading.Thread(
                target=self._worker,
                args=(proxy,),
                name=f"Worker-{proxy}"
            )
            thread.start()
            self.threads.append(thread)
            
        logger.info(f"Started {len(self.threads)} worker threads")
        
        try:
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Stopping all workers...")
            self.stop()

    def stop(self):
        self.running = False
        for thread in self.threads:
            thread.join()
        logger.info("All workers stopped")

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
                    logger.info(f"Berhasil mendapatkan UID: {uid}")
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

    except RequestException as e:
        logger.error(f"Kesalahan jaringan saat mendapatkan UID: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Kesalahan tidak terduga saat mendapatkan UID: {str(e)}")
        return None

def main():
    token = os.getenv("TOKEN")
    user_uid = os.getenv("UID")
    
    if not token or not user_uid:
        logger.error("Missing required environment variables")
        return
    
    pinger = AigaeaPinger(token, user_uid, "proxy.txt")
    pinger.start()

if __name__ == "__main__":
    main()