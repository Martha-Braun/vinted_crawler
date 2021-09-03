# coding=utf-8
import sys

sys.path.append("/Users/marthab/vinted_crawler/vinted_crawler")

import pandas as pd
import numpy as np
import logging

import time
import datetime
from tqdm import tqdm

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver import ActionChains
from selenium.common.exceptions import NoSuchElementException

import gspread
from df2gspread import df2gspread as d2g
from oauth2client.service_account import ServiceAccountCredentials
import gspread_dataframe as gd

from confidential.conf_constants import *

logger = logging.getLogger(__name__)


class VintedCrawler:
    def __init__(self):
        # to be created
        self.product_details_today = None

    def __create_instance(self):
        # setting up chrome options
        chrome_options = Options()
        # browsing in incognito mode
        chrome_options.add_argument("--incognito")
        # setting window size to 1920x1080
        chrome_options.add_argument("--window-size=1920x1080")

        # create instance
        driver = webdriver.Chrome(
            chrome_options=chrome_options,
            executable_path="/Users/marthab/Desktop/Python_Labs/vinted_crawler/chromedriver",
        )

        # set url to Women > Jacquemus > filter:newest first
        url = "https://www.vinted.de/vetements?brand_id[]=168278&catalog[]=1904&order=newest_first"
        driver.get(url)

        # wait 2 sec for page to fully load
        time.sleep(2)

        # don't accept cookies
        try:
            # privatsphaere-einstellung alle ablehnen
            reject_all_button = driver.find_element_by_css_selector(
                "#onetrust-reject-all-handler"
            )
            ActionChains(driver).click(reject_all_button).perform()
        # NoSuchElementException thrown if not present
        except NoSuchElementException:
            print("Not asked for privacy settings")

        # choose country Germany
        try:
            germany_button = driver.find_element_by_xpath(
                "/html/body/div[13]/div/div/div/div[3]/div[3]/div[2]/div/h2/span"
            )
            ActionChains(driver).click(germany_button).perform()
        except NoSuchElementException:
            print("Not asked for country")

        # wait 2 sec for page to fully load
        time.sleep(2)

        return driver

    def get_product_details(self):

        logging.info("Creating Instance")
        # create instance and decline cookies
        driver = self.__create_instance()

        logging.info("Getting product URLs of all products on first 5 pages...")
        # get url of all products on first 5 pages
        product_urls = []
        for page in range(1, 5, 1):
            page_url = f"https://www.vinted.de/vetements?brand_id[]=168278&catalog[]=1904&order=newest_first&page={page}"
            driver.get(page_url)
            products = driver.find_elements_by_css_selector("a.ItemBox_overlay__1kNfX")
            product_urls_page = [prod.get_attribute("href") for prod in products]
            product_urls.extend(product_urls_page)

        # scraping individual product details
        product_details = []
        today = datetime.datetime.now().date()
        yesterday = today - datetime.timedelta(days=1)

        for product_url in tqdm(product_urls):
            driver.get(product_url)

            # get upload_date and stop for loop if item was uploaded more than 1 day ago
            upload_date_full = driver.find_element_by_xpath(
                "//div[@class='details-list__item-value']/time"
            ).get_attribute("datetime")
            upload_date = datetime.datetime.strptime(
                upload_date_full, "%Y-%m-%dT%H:%M:%S%z"
            ).date()
            if upload_date != yesterday and upload_date != today:
                break

            # get product id from url
            product_id = product_url.split("/")[-1]

            # get product subcatgory from url
            product_subcat = product_url.split("/")[-2]

            # get product catgory from url
            product_cat = product_url.split("/")[-3]

            # get brand
            brand = driver.find_element_by_xpath(
                "//a[@itemprop='url']/span[@itemprop='name']"
            ).text

            # get price
            price = driver.find_element_by_xpath(
                "/html/body/div[5]/div/section/div/div[2]/main/aside/div[1]/div[1]/div[1]/div[1]/span/div"
            ).text

            # get size
            try:
                size_check = driver.find_element_by_xpath(
                    "//div[@class='details-list__item u-position-relative']/div[contains(text(), 'Größe')]"
                )
                size = driver.find_element_by_xpath(
                    "/html/body/div[5]/div/section/div/div[2]/main/aside/div[1]/div[1]/div[2]/div[2]/div[2]"
                ).text
            except NoSuchElementException:
                size = "-"

            # get item condition
            try:
                condition = driver.find_element_by_xpath(
                    "//div[@itemprop='itemCondition']"
                ).text
            except:
                condition = "-"

            # get colour
            try:
                colour = driver.find_element_by_xpath("//div[@itemprop='color']").text
            except NoSuchElementException:
                colour = "-"

            infos = {
                "Upload_date": upload_date,
                "Product_Id": product_id,
                "Category": product_cat,
                "Sub_Category": product_subcat,
                "Brand": brand,
                "Price": price,
                "Size": size,
                "Condition": condition,
                "Colour": colour,
                "URL": product_url,
            }

            product_details.append(infos)

        logging.info("Product Details saved to DataFrame...")
        product_details_df = pd.DataFrame(product_details)

        # get product_details_df from yesterday only if yesterday files exists
        date_suffix_yes = "".join(str(yesterday).split("-"))
        try:
            product_details_df_old = pd.read_csv(
                f"vinted_crawler/data/{date_suffix_yes}_product_details.csv",
                index_col=0,
            )

            # get elements in product_details_df_new that are NOT in product_details_df_old
            new_non_duplicate = np.setdiff1d(
                list(product_details_df["Product_Id"]),
                list(product_details_df_old["Product_Id"]),
            )

            # save product_details_df, keep only product_ids that were not in yesterdays df
            date_suffix = "".join(str(today).split("-"))
            filt = product_details_df["Product_Id"].isin(list(new_non_duplicate))
            product_details_df[filt].to_csv(
                f"vinted_crawler/data/{date_suffix}_product_details.csv"
            )
            self.product_details_today = product_details_df[filt].copy()

        except:
            self.product_details_today = product_details_df.copy()

    def import_to_gs(self):
        # import google credentials
        scope = [SPSH_URL, GAPI_URL]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(GKEY_PATH, scope)
        gc = gspread.authorize(credentials)
        spreadsheet_key = SPSH_KEY
        wks_name = "crawler_output"

        ws = gc.open_by_key(spreadsheet_key).worksheet(wks_name)

        logging.info("Uploading New DataFrame to Google Sheets")
        # add as many rows as new dataframe has
        empty_row = ["" for cell in range(ws.col_count)]
        for row in range(self.product_details_today.shape[0]):
            ws.insert_row(empty_row, index=2)

        # upload new df to google sheet
        gd.set_with_dataframe(
            worksheet=ws,
            dataframe=self.product_details_today,
            include_index=False,
            include_column_header=False,
            row=2,
            resize=False,
        )
