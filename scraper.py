from playwright.sync_api import sync_playwright
import pandas as pd
import time
import datetime
import os


def get_business_urls(page):
    """
    Scrapes all business URLs from the current list results.
    """
    try:
        page.wait_for_selector('a[href*="/maps/place/"]', timeout=2000)
    except:
        return []

    links = page.locator('a[href*="/maps/place/"]').evaluate_all(
        "els => els.map(e => e.href)"
    )
    return links


def scroll_to_bottom(page):
    try:
        page.wait_for_selector('div[role="feed"]', timeout=3000)
        previous_height = 0
        while True:
            feed = page.locator('div[role="feed"]')
            feed.evaluate("element => element.scrollTop = element.scrollHeight")
            time.sleep(2)
            current_height = feed.evaluate("element => element.scrollHeight")
            if current_height == previous_height:
                break
            previous_height = current_height
    except:
        pass


def extract_details_from_url(page, url):
    data = {
        "Name": "",
        "Ratings": "",
        "Niche": "",
        "Address": "",
        "Timings": "",
        "Contact": "",
        "Website": "",
    }

    try:
        page.goto(url, timeout=60000)
        page.wait_for_load_state("domcontentloaded")
        try:
            page.wait_for_selector("h1", timeout=5000)
        except:
            pass

        if page.locator("h1").count() > 0:
            data["Name"] = page.locator("h1").first.inner_text()

        rating_loc = page.locator('div[role="img"][aria-label*="stars"]')
        if rating_loc.count() > 0:
            data["Ratings"] = rating_loc.first.get_attribute("aria-label")

        cat_btn = page.locator('button[jsaction*="category"]').first
        if cat_btn.count() > 0:
            data["Niche"] = cat_btn.inner_text()

        addr_btn = page.locator('button[data-item-id="address"]')
        if addr_btn.count() > 0:
            data["Address"] = addr_btn.get_attribute("aria-label").replace(
                "Address: ", ""
            )

        web_btn = page.locator('a[data-item-id="authority"]')
        if web_btn.count() > 0:
            data["Website"] = web_btn.get_attribute("href")

        phone_btn = page.locator('button[data-item-id*="phone"]')
        if phone_btn.count() > 0:
            data["Contact"] = phone_btn.get_attribute("aria-label").replace(
                "Phone: ", ""
            )

        hours_div = page.locator(
            'div[aria-label*="Hide open hours"], div[aria-label*="Show open hours"]'
        )
        if hours_div.count() > 0:
            data["Timings"] = hours_div.get_attribute("aria-label")

    except Exception as e:
        print(f"Error extracting {url}: {e}")

    return data


def save_data(data):
    if not data:
        return

    output_file = "/Users/raksh/Desktop/maps_results.xlsx"
    out_df = pd.DataFrame(data)

    columns = [
        "Name",
        "Ratings",
        "Niche",
        "Address",
        "Timings",
        "Contact",
        "Website",
        "Keyword",
    ]
    final_cols = [c for c in columns if c in out_df.columns]
    out_df = out_df[final_cols]

    try:
        out_df.to_excel(output_file, index=False)
        print(f"Saved {len(out_df)} records to: {output_file}")
        print(f"File exists? {os.path.exists(output_file)}")
    except Exception as e:
        print(f"Error saving to {output_file}: {e}")


def main():
    input_file = "keywords.xlsx"
    print("Using keywords.xlsx for scraping")

    try:
        df = pd.read_excel(input_file)
        if "status" not in df.columns:
            df["status"] = ""
    except Exception as e:
        print("Error reading keywords file:", e)
        return

    all_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.google.com/maps")

        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        try:
            consent = page.locator(
                'button[aria-label="Accept all"], button:has-text("Accept all"), button:has-text("Accept")'
            )
            if consent.count() > 0:
                consent.first.click()
                page.wait_for_timeout(2000)
        except:
            pass

        for index, row in df.iterrows():
            if row.get("status") == "DONE":
                continue

            k = row["keyword"]
            print(f"Processing Keyword: {k}")

            try:
                page.wait_for_selector("input", timeout=5000)

                sb = page.locator("input#searchboxinput")
                if not sb.is_visible():
                    sb = page.get_by_role("combobox", name="Search Google Maps")
                if not sb.is_visible():
                    sb = page.locator('input[aria-label="Search Google Maps"]')

                if not sb.is_visible():
                    inputs = page.locator("input").all()
                    visible = [i for i in inputs if i.is_visible()]
                    if len(visible) == 1:
                        sb = visible[0]
                    else:
                        # try just finding generic search box by placeholder?
                        sb = page.locator('input[placeholder*="Search"]')
                        if not sb.is_visible():
                            raise Exception("Search box not found")

                sb.fill(str(k))
                page.keyboard.press("Enter")
                page.wait_for_timeout(3000)
            except Exception as e:
                print("Search failed:", e)
                try:
                    # One last try: blindly type if assume focus?
                    page.keyboard.type(str(k))
                    page.keyboard.press("Enter")
                except:
                    continue
                continue

            collected_urls = set()

            while True:
                scroll_to_bottom(page)

                urls = get_business_urls(page)
                new_urls = [u for u in urls if u not in collected_urls]

                # If we found no URLs, maybe we are not on results list?
                # But we just wait for whatever we can find.

                collected_urls.update(new_urls)
                print(
                    f"  Collected {len(new_urls)} new URLs. Total: {len(collected_urls)}"
                )

                # If total is 0, maybe try looking for direct listing (if single result)?
                if len(collected_urls) == 0:
                    # Check if we are already on a detail page?
                    if "/maps/place/" in page.url:
                        collected_urls.add(page.url)
                        break

                if len(new_urls) == 0 and len(collected_urls) > 0:
                    # No new URLs after scroll. End
                    break

                # Stop if we have enough for testing ?
                if "test_keywords" in input_file and len(collected_urls) >= 5:
                    print("  Limit reached for test.")
                    break

                next_btn = page.locator('button[aria-label="Next page"]')
                if next_btn.is_visible() and next_btn.is_enabled():
                    next_btn.click()
                    page.wait_for_timeout(3000)
                else:
                    break

            print(f"  Extracting details for {len(collected_urls)} businesses...")
            for idx, url in enumerate(collected_urls):
                try:
                    print(f"    [{idx + 1}/{len(collected_urls)}] Visiting {url}...")
                    details = extract_details_from_url(page, url)
                    details["Keyword"] = k
                    all_data.append(details)
                    time.sleep(1)
                except Exception as e:
                    print(f"    Error processing URL {url}: {e}")

            # Incremental save
            if len(all_data) > 0:
                print(all_data[-1])  # Print last record as sample
            save_data(all_data)

            # Update status in keywords file
            df.at[index, "status"] = "DONE"
            try:
                df.to_excel(input_file, index=False)
                print(f"Marked '{k}' as DONE in {input_file}")
            except Exception as e:
                print(f"Error saving status to {input_file}: {e}")

        browser.close()

    if not all_data:
        print("No data extracted. Extraction selectors may be broken.")
    else:
        # Final save
        save_data(all_data)


if __name__ == "__main__":
    main()
