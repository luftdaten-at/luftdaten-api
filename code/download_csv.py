import requests
import re
import gzip
import os
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from enums import SensorModel
from tqdm import tqdm


def download(url, trys = 5):
    """
    Downloads a file from the given URL, extracts if .csv.gz, and saves as .csv.
    """
    csv_filename = url.split("/")[-1].removesuffix('.gz')
    raw = None
    for _ in range(trys):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            raw = response.raw
            break
        except Exception:
            continue

    if not raw:
        print(f'Faild to download File: {csv_filename}')
        return
    
    with open(os.path.join(download_folder, csv_filename), 'wb') as csv_file:
        file_content = gzip.GzipFile(fileobj=raw) if url.endswith('.gz') else raw
        csv_file.write(file_content.read())

    return csv_filename


def list_website(url, trys = 5):
    page = None

    for _ in range(trys):
        try:
            response = requests.get(url)
            response.raise_for_status()
            page = response.text
            break
        except Exception:
            continue

    if not page:
        print(f'Faild to list: {url}')
        return

    soup = BeautifulSoup(page, "html.parser")
    # walk into all months
    for item in reversed(soup.find_all("a")):
        link = item.get("href")
        if re.fullmatch(pattern_day, link):
            list_website(urljoin(url, link)) 
        if re.fullmatch(pattern_year, link):
            list_website(urljoin(url, link))
        if link.endswith(".csv") or link.endswith(".gz"):
            for sensor_name in SensorModel._names.values():
                if sensor_name.lower() in link:
                    break
            else:
                continue
            all_csv_urls.append(urljoin(url, link))
            print(urljoin(url, link), file=open('download_list.txt', 'a'))


download_folder = "sensor_community_archive"
pattern_day = r"\d\d\d\d-\d\d-\d\d/"
pattern_year = r"\d\d\d\d/"
URL = "https://archive.sensor.community/"
all_csv_urls = []


def main():
    # list all csv files witch have sensors that we need
    list_website(URL)
    # download all files
    # Progress bar and download loop
    for url in tqdm(all_csv_urls, desc="Downloading files", unit="file"):
        download(url)


if __name__ == '__main__':
    main()
