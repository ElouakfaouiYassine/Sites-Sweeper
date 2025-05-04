import os
import threading
import hashlib
import webbrowser
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from tkinter import Tk, Label, Entry, Button, Listbox, Frame, END, ttk, messagebox, StringVar
from tkinter.scrolledtext import ScrolledText
from playwright.sync_api import sync_playwright
from datetime import datetime

class SiteSweeper:
    def __init__(self, root):
        self.root = root
        self.visited = set()
        self.output_dir = "offline_pages"
        self.assets_dir = os.path.join(self.output_dir, "assets")
        self.setup_ui()
        self.create_directories()
        
    def setup_ui(self):
        self.root.title("🧹 Site Sweeper")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Configure styles
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, font=('Arial', 10))
        self.style.configure("TLabel", font=('Arial', 10))
        self.style.configure("TEntry", font=('Arial', 10))
        
        # Main frame
        main_frame = Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # URL input frame
        input_frame = Frame(main_frame)
        input_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(input_frame, text="Website URL:").pack(side='left', padx=(0, 5))
        
        self.url_var = StringVar()
        self.url_entry = ttk.Entry(input_frame, textvariable=self.url_var, width=50)
        self.url_entry.pack(side='left', expand=True, fill='x', padx=(0, 5))
        
        self.start_btn = ttk.Button(input_frame, text="Start Sweep", command=self.start_sweep)
        self.start_btn.pack(side='left', padx=(0, 5))
        
        self.open_btn = ttk.Button(input_frame, text="Open Results", command=self.open_index, state='disabled')
        self.open_btn.pack(side='left')
        
        
        self.progress_var = StringVar(value="Ready")
        self.progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        self.progress_label.pack(fill='x', pady=(0, 5))
        
        self.progress = ttk.Progressbar(main_frame, orient='horizontal', mode='determinate')
        self.progress.pack(fill='x', pady=(0, 10))
        
        
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        
        working_frame = Frame(self.notebook)
        self.notebook.add(working_frame, text="✅ Working Links")
        
        self.working_list = Listbox(working_frame, font=('Arial', 10), fg='green')
        self.working_list.pack(fill='both', expand=True, padx=5, pady=5)
        
        
        broken_frame = Frame(self.notebook)
        self.notebook.add(broken_frame, text="❌ Broken Links")
        
        self.broken_list = Listbox(broken_frame, font=('Arial', 10), fg='red')
        self.broken_list.pack(fill='both', expand=True, padx=5, pady=5)
        
        
        log_frame = Frame(self.notebook)
        self.notebook.add(log_frame, text="📝 Log")
        
        self.log_text = ScrolledText(log_frame, font=('Arial', 9), wrap='word')
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)
        self.log_text.config(state='disabled')
        
        
        self.status_var = StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief='sunken', anchor='w')
        status_bar.pack(fill='x', side='bottom', ipady=2)
        
        
        self.root.bind('<Return>', lambda e: self.start_sweep())
        
    def create_directories(self):
        os.makedirs(self.assets_dir, exist_ok=True)
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state='normal')
        self.log_text.insert(END, f"[{timestamp}] {message}\n")
        self.log_text.config(state='disabled')
        self.log_text.see(END)
        self.root.update_idletasks()
        
    def sanitize_filename(self, url, is_main=False):
        return "index.html" if is_main else hashlib.md5(url.encode()).hexdigest() + ".html"
        
    def download_resources(self, soup, base_url):
        tags = {"img": "src", "link": "href", "script": "src"}
        for tag, attr in tags.items():
            for el in soup.find_all(tag):
                url = el.get(attr)
                if not url: 
                    continue
                full_url = urljoin(base_url, url)
                filename = os.path.basename(urlparse(full_url).path)
                if not filename: 
                    continue
                local_path = os.path.join(self.assets_dir, filename)
                try:
                    self.log(f"Downloading resource: {full_url}")
                    content = requests.get(full_url, timeout=5).content
                    with open(local_path, "wb") as f:
                        f.write(content)
                    el[attr] = os.path.join("assets", filename)
                except Exception as e:
                    self.log(f"Failed to download {full_url}: {str(e)}")
        return soup
        
    def update_links(self, soup, stem):
        for a in soup.find_all("a", href=True):
            full_url = urljoin(stem, a['href'])
            if full_url.startswith(stem):
                a['href'] = self.sanitize_filename(full_url)
        return soup
        
    def save_html(self, url, html, is_main=False):
        filename = self.sanitize_filename(url, is_main)
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        self.log(f"Saved page: {filename}")
        
    def fetch_html(self, url):
        try:
            self.log(f"Fetching: {url}")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=20000)
                page.wait_for_load_state("networkidle")
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            self.log(f"Error fetching {url}: {str(e)}")
            return None
        
    def process_page(self, url, stem, is_main=False):
        try:
            html = self.fetch_html(url)
            if not html:
                return set()
                
            soup = BeautifulSoup(html, 'html.parser')
            soup = self.download_resources(soup, url)
            soup = self.update_links(soup, stem)
            self.save_html(url, str(soup), is_main)

            base = "{0.scheme}://{0.netloc}".format(urlparse(url))
            return {urljoin(base, a['href']) for a in soup.find_all("a", href=True) 
                    if urljoin(base, a['href']).startswith(stem)}
        except Exception as e:
            self.log(f"Error processing {url}: {str(e)}")
            return set()
        
    def sweep(self, url, stem, is_main=False):
        if url in self.visited: 
            return
        self.visited.add(url)
        self.progress_var.set(f"Processing: {url}")
        self.progress['value'] = len(self.visited)
        
        links = self.process_page(url, stem, is_main)
        for link in links:
            if link not in self.visited:
                self.sweep(link, stem)
                
    def start_sweep(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
            
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
            
        self.visited.clear()
        self.clean_folder()
        self.working_list.delete(0, END)
        self.broken_list.delete(0, END)
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, END)
        self.log_text.config(state='disabled')
        
        self.start_btn.config(state='disabled')
        self.open_btn.config(state='disabled')
        self.progress['maximum'] = 100
        self.status_var.set("Sweeping...")
        
        threading.Thread(target=self.run_sweep, args=(url,), daemon=True).start()
        
    def run_sweep(self, url):
        try:
            self.log("Starting sweep...")
            self.sweep(url, url, True)
            
            working, broken = [], []
            total = len(self.visited)
            self.progress['maximum'] = total
            
            for i, link in enumerate(self.visited):
                try:
                    self.progress_var.set(f"Checking link {i+1}/{total}: {link}")
                    self.progress['value'] = i + 1
                    
                    response = requests.get(link, timeout=3)
                    if response.status_code == 200:
                        working.append(link)
                    else:
                        broken.append(link)
                        self.log(f"Broken link ({response.status_code}): {link}")
                except Exception as e:
                    broken.append(link)
                    self.log(f"Error checking link {link}: {str(e)}")
                    
            self.working_list.delete(0, END)
            self.broken_list.delete(0, END)
            
            for link in working: 
                self.working_list.insert(END, link)
            for link in broken: 
                self.broken_list.insert(END, link)
                
            self.status_var.set(f"Finished! {len(working)} working, {len(broken)} broken links")
            self.log(f"Sweep completed. {len(working)} working, {len(broken)} broken links")
            
        except Exception as e:
            self.log(f"Error during sweep: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
        finally:
            self.start_btn.config(state='normal')
            self.open_btn.config(state='normal')
            self.progress_var.set("Ready")
            
    def clean_folder(self):
        if os.path.exists(self.output_dir):
            for root, dirs, files in os.walk(self.output_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for d in dirs:
                    os.rmdir(os.path.join(root, d))
        self.create_directories()
        self.log("Cleaned output directory")
        
    def open_index(self):
        index_path = os.path.abspath(os.path.join(self.output_dir, "index.html"))
        if os.path.exists(index_path):
            webbrowser.open(f"file://{index_path}")
        else:
            messagebox.showwarning("Warning", "No index.html file found. Run a sweep first.")

if __name__ == "__main__":
    root = Tk()
    app = SiteSweeper(root)
    root.mainloop()