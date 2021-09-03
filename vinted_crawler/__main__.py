from vinted_crawler.crawler.vinted_spider import VintedCrawler


def main():
    # instancing crawler class
    vinted_crawler = VintedCrawler()

    # get product details and save df
    vinted_crawler.get_product_details()

    # upload product details to GS
    vinted_crawler.import_to_gs()


if __name__ == "__main__":
    main()
