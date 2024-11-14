from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin
import re
import zipfile
import io
import pandas as pd


def import_sensor_community_archive_from_csv(csv: str):
    df = pd.read_csv(io.BytesIO(csv.encode()), encoding='utf8', sep=";")
    print(df)


url = "https://archive.sensor.community/csv_per_month/"

page = requests.get(url).text

soup = BeautifulSoup(page, "html.parser")
pattern = r"\d\d\d\d-\d\d"

def walk(url):
    sub_soup = BeautifulSoup(requests.get(url).text, "html.parser")
    for item in sub_soup.find_all("a"):
        if item.get("href").endswith(".zip"):
            # download and extract
            # pass to import_sensor_community()
            response = requests.get(urljoin(url, item.get("href")))
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                for file_name in zip_file.namelist():
                    with zip_file.open(file_name) as file:
                        file_content = file.read().decode('utf-8')  # Decode if it's a text file
                        print(f"Import file: {file_name}")
                        import_sensor_community_archive_from_csv(file_content)

for item in soup.find_all("a"):
    if re.match(pattern, item.get("href")):
        walk(urljoin(url, item.get("href"))) 
        break
