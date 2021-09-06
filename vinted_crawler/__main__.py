from vinted_crawler.crawler.vinted_spider import VintedCrawler
from vinted_crawler.constants.website_constants import *


def main():
    # instancing crawler class
    vinted_crawler = VintedCrawler()

    # set instance
    vinted_crawler.create_instance()

    # get product details and save df for each brand
    for brand in BRAND_LIST:
        vinted_crawler.get_product_details(brand)

        # upload product details to GS
        vinted_crawler.import_to_gs(brand)


if __name__ == "__main__":
    main()
