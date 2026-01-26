from playwright.sync_api import sync_playwright


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Headless=False to match scraper
        page = browser.new_page()
        page.goto("https://www.google.com/maps")
        page.wait_for_timeout(10000)

        print("Page Title:", page.title())

        # Check for inputs
        inputs = page.locator("input").all()
        print(f"Found {len(inputs)} inputs.")
        for i, inp in enumerate(inputs):
            try:
                id_ = inp.get_attribute("id")
                aria = inp.get_attribute("aria-label")
                placeholder = inp.get_attribute("placeholder")
                print(
                    f"Input {i}: ID='{id_}', Aria='{aria}', Placeholder='{placeholder}'"
                )
            except:
                pass

        browser.close()


if __name__ == "__main__":
    run()
