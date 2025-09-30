from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import requests
from datetime import datetime
import random
import re
from concurrent.futures import ThreadPoolExecutor
import threading

class TargetSeleniumMonitor:
    def __init__(self, webhook_url=None, num_threads=8):
        self.webhook_url = webhook_url
        self.products = []
        self.num_threads = num_threads
        self.driver_pool = []
        self.driver_lock = threading.Lock()
        
        # Pre-create driver pool for maximum speed
        print(f"🔥 Initializing {num_threads} browser instances...")
        for i in range(num_threads):
            self.driver_pool.append(self.create_driver())
            print(f"  ✓ Browser {i+1}/{num_threads} ready")
        
    def create_driver(self):
        """Create an optimized Chrome driver instance"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-images')  # Don't load images (faster)
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Performance preferences
        prefs = {
            'profile.managed_default_content_settings.images': 2,  # Don't load images
            'profile.default_content_setting_values.notifications': 2,
            'profile.managed_default_content_settings.stylesheets': 2,  # Don't load CSS
        }
        chrome_options.add_experimental_option('prefs', prefs)
        
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0'
        ]
        chrome_options.add_argument(f'user-agent={random.choice(user_agents)}')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(10)  # Timeout after 10s
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
        
    def add_product(self, url, name, cart_limit=None):
        """Add a product with optional manual cart limit"""
        self.products.append({
            'url': url,
            'name': name,
            'cart_limit': cart_limit,
            'last_status': None
        })
    
    def get_cart_limit_fast(self, driver):
        """Fast cart limit detection"""
        try:
            page_text = driver.page_source.lower()
            product_name = driver.title.lower()
            
            # Quick category detection
            if 'pokemon' in product_name or 'pokémon' in product_name or 'trading card' in product_name:
                return '20'
            elif any(term in product_name for term in ['playstation', 'xbox', 'nintendo', 'console']):
                return '2'
            
            # Quick text search
            limit_match = re.search(r'limit\s+(\d+)', page_text)
            if limit_match:
                return limit_match.group(1)
        except:
            pass
        
        return '10'
        
    def extract_product_data_fast(self, product, driver):
        """Fast extraction - minimal processing"""
        product_data = {
            'price': 'N/A',
            'image': None,
            'stock_level': 'I+',
            'cart_limit': product.get('cart_limit', '10')
        }
        
        try:
            page_source = driver.page_source
            
            # Fast price extraction
            price_match = re.search(r'\$(\d+\.\d{2})', page_source)
            if price_match:
                product_data['price'] = f'${price_match.group(1)}'
            
            # Fast stock level
            if 'only' in page_source.lower() and 'left' in page_source.lower():
                stock_match = re.search(r'only\s+(\d+)\s+left', page_source.lower())
                if stock_match:
                    product_data['stock_level'] = f'{stock_match.group(1)} Left'
                else:
                    product_data['stock_level'] = 'Low'
            elif 'limited stock' in page_source.lower():
                product_data['stock_level'] = 'Limited'
            
            # Get cart limit if not set
            if not product.get('cart_limit'):
                product_data['cart_limit'] = self.get_cart_limit_fast(driver)
            
            # Try to get image URL (but don't fail if we can't)
            img_match = re.search(r'target\.scene7\.com[^"\']+', page_source)
            if img_match:
                product_data['image'] = f'https://{img_match.group(0)}'
                
        except:
            pass
        
        return product_data
        
    def check_product_ultrafast(self, args):
        """Ultra-fast product check"""
        product, driver_index = args
        driver = self.driver_pool[driver_index]
        
        try:
            driver.get(product['url'])
            time.sleep(1.5)  # Reduced wait time
            
            is_available = False
            status = "OUT_OF_STOCK"
            
            page_source = driver.page_source.lower()
            
            # Fast availability check
            if "out of stock" in page_source or "sold out" in page_source:
                status = "OUT_OF_STOCK"
            else:
                # Quick button check
                try:
                    buttons = driver.find_elements(By.TAG_NAME, 'button')
                    for btn in buttons:
                        btn_text = btn.text.lower()
                        if 'add to cart' in btn_text or 'ship it' in btn_text:
                            if not btn.get_attribute('disabled'):
                                is_available = True
                                status = "IN_STOCK"
                                break
                except:
                    pass
            
            # Send alert only on restock
            if is_available and product['last_status'] == 'OUT_OF_STOCK':
                product_data = self.extract_product_data_fast(product, driver)
                self.send_alert(product, product_data)
                print(f"🚨 RESTOCK: {product['name'][:50]}")
            
            product['last_status'] = status
            return (product['name'][:30], status)
            
        except Exception as e:
            return (product['name'][:30], f"ERROR: {str(e)[:20]}")
    
    def send_alert(self, product, product_data):
        if not self.webhook_url:
            return
        
        tcin = product['url'].split('/-/A-')[-1]
        
        embed = {
            'author': {
                'name': 'Target Restocks',
                'icon_url': 'https://i.imgur.com/lHQNiKE.png'
            },
            'title': product['name'],
            'url': product['url'],
            'color': 0xCC0000,
            'fields': [
                {'name': 'Price', 'value': product_data['price'], 'inline': True},
                {'name': 'Type', 'value': 'Restock', 'inline': True},
                {'name': 'Tcin', 'value': tcin, 'inline': True},
                {'name': 'Total Stock', 'value': product_data['stock_level'], 'inline': True},
                {'name': 'Open In App', 'value': f'[Click Me](https://target.com/p/-/A-{tcin})', 'inline': True},
                {'name': 'Cart Limit', 'value': product_data['cart_limit'], 'inline': True},
                {'name': 'Links', 'value': f'[Cart](https://www.target.com/cart) | [Lightning](https://www.target.com/c/target-deals/-/N-4ttke) | [Mobile](https://target.com/p/-/A-{tcin}) | [Ebay](https://www.ebay.com/sch/i.html?_nkw={product["name"].replace(" ", "+")}) | [Ebay Sales](https://www.ebay.com/sch/i.html?_nkw={product["name"].replace(" ", "+")}&LH_Sold=1&LH_Complete=1)', 'inline': False}
            ],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if product_data['image']:
            embed['thumbnail'] = {'url': product_data['image']}
        
        try:
            requests.post(self.webhook_url, json={'content': '@everyone', 'embeds': [embed]}, timeout=3)
        except:
            pass
    
    def run(self, check_interval=2):
        print("\n" + "="*60)
        print("⚡⚡⚡ ZEPHYR-SPEED TARGET MONITOR ⚡⚡⚡")
        print("="*60)
        print(f"Check interval: {check_interval}s")
        print(f"Concurrent threads: {self.num_threads}")
        print(f"Monitoring: {len(self.products)} products")
        print(f"Mode: MAXIMUM SPEED")
        print("="*60 + "\n")
        
        try:
            cycle = 0
            while True:
                cycle += 1
                start_time = time.time()
                
                print(f"⚡ Cycle #{cycle} | {datetime.now().strftime('%H:%M:%S')}")
                
                # Assign products to threads in a round-robin fashion
                tasks = []
                for i, product in enumerate(self.products):
                    driver_index = i % self.num_threads
                    tasks.append((product, driver_index))
                
                # Execute all checks in parallel
                with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
                    results = list(executor.map(self.check_product_ultrafast, tasks))
                
                # Display results compactly
                in_stock = sum(1 for _, status in results if status == "IN_STOCK")
                out_of_stock = sum(1 for _, status in results if status == "OUT_OF_STOCK")
                
                elapsed = time.time() - start_time
                print(f"  ✅ {in_stock} in stock | ❌ {out_of_stock} OOS | ⏱️ {elapsed:.2f}s")
                
                # Sleep for remaining time
                sleep_time = max(0, check_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print("\n\n👋 Stopping monitor...")
            for driver in self.driver_pool:
                try:
                    driver.quit()
                except:
                    pass
            print("✓ All browsers closed")

webhook = "https://discordapp.com/api/webhooks/1421254695644696667/i7WP5OliQKlyfm1ywlQAwpebazBchPCtHb777JzSENt9utRJyWf7TGZerFjXRRya2eJT"

# 8 threads for maximum parallelization
monitor = TargetSeleniumMonitor(webhook_url=webhook, num_threads=8)

print("\n📦 Adding products...")
monitor.add_product('https://www.target.com/p/-/A-91619960', 'Pokemon Twilight Masquerade ETB')
monitor.add_product('https://www.target.com/p/-/A-1005019724', 'Pokemon Trick or Trade')
monitor.add_product('https://www.target.com/p/-/A-93954446', 'Target Product 93954446')
monitor.add_product('https://www.target.com/p/-/A-94336414', 'Target Product 94336414')
monitor.add_product('https://www.target.com/p/-/A-94300069', 'Target Product 94300069')
monitor.add_product('https://www.target.com/p/-/A-94864079', 'Target Product 94864079')
monitor.add_product('https://www.target.com/p/-/A-94681763', 'Target Product 94681763')
monitor.add_product('https://www.target.com/p/-/A-94300067', 'Target Product 94300067')
monitor.add_product('https://www.target.com/p/-/A-94681777', 'Target Product 94681777')
monitor.add_product('https://www.target.com/p/-/A-94681773', 'Target Product 94681773')
monitor.add_product('https://www.target.com/p/-/A-94270152', 'Target Product 94270152')
monitor.add_product('https://www.target.com/p/-/A-94898411', 'Target Product 94898411')
monitor.add_product('https://www.target.com/p/-/A-94898402', 'Target Product 94898402')
monitor.add_product('https://www.target.com/p/-/A-94681766', 'Target Product 94681766')
monitor.add_product('https://www.target.com/p/-/A-94681782', 'Target Product 94681782')
monitor.add_product('https://www.target.com/p/-/A-94898406', 'Target Product 94898406')
monitor.add_product('https://www.target.com/p/-/A-94721096', 'Target Product 94721096')
print(f"✓ Added {len(monitor.products)} products\n")

# ZEPHYR MODE: 2 second checks with 8 browsers
monitor.run(check_interval=2)
