import asyncio
import csv
from playwright.async_api import Playwright, async_playwright, expect
from web_agent import JoshyTrain
from utils.json_utils import extract_json
import argparse


async def login(page, username: str, password: str) -> None:
    """Function to handle login."""
    joshyTrain = JoshyTrain(page)
    await page.goto(
        "https://www.imarkportal.com/ecmvc/portal/auth/login?ReturnUrl=%2fecmvc"
    )
    await page.locator("input[type='text']").fill(username)
    await page.locator("input[type='password']").fill(password)
    await page.get_by_label("Log In").click()
    await page.wait_for_timeout(5000)
    response = await joshyTrain.chat(
        """Is the login successful? The login is ONLY failed if the page SPECIFICALLY shows that the login has failed. Respond in the following JSON format: {"login": "true or false"}"""
    )
    data = extract_json(response)
    if data["login"] == "false":
        await page.screenshot(path="screenshot.jpg", full_page=True)
        raise Exception("Incorrect login credentials")
    await page.get_by_role("link", name="Online Ordering").click()
    async with page.expect_popup() as page_info:
        page = await page_info.value
    try:
        # Wait for the element with text "Reset Filters" to be present in the DOM
        await page.wait_for_selector(
            'text="Reset Filters"', state="attached", timeout=15000
        )  # Adjust the timeout as needed
        await page.locator('text="Reset Filters"').click()
        print('"Reset Filters" clicked.')
    except Exception as e:
        # If the element isn't found within the timeout, just move on
        print('"Reset Filters" not found within timeout or not clickable. Moving on.')
    return page


async def process_item(
    page, upc: str, filename: str, row_index: int, total_packs, pack_size
) -> None:
    """Function to process the item based on UPC."""
    if not upc:
        update_csv_cell(
            filename, row_index, "name_ordered", "zzzMissing UPC"
        )  # Assuming 0-based index for rows
        return

    try:
        await page.wait_for_timeout(3000)
        await page.get_by_role("textbox").fill(upc)
        await page.get_by_role("textbox").press("Enter")
        await page.wait_for_timeout(5000)

        # Locate all .btn-link elements within the context of .general-info-content.flex-centered-vertical
        btn_links = await page.locator(
            ".general-info-content.flex-centered-vertical .btn-link"
        ).element_handles()
        for btn_link in btn_links:
            # Get the parent item card of each .btn-link
            item_card = await btn_link.query_selector(
                'xpath=ancestor::div[contains(@class, "general-info-content")][contains(@class, "flex-centered-vertical")]'
            )

            # Check if the item card contains text elements with "Out of Stock"
            out_of_stock = await item_card.query_selector('text="Out of Stock"')

            if not out_of_stock:
                # This item is in stock; click the .btn-link within this card
                await btn_link.click()
                await page.wait_for_timeout(3000)
                print("Clicked on the .btn-link of the first available item.")

                item_name = await order_item(
                    page, total_packs, pack_size
                )  # Proceed to order the item
                update_csv_cell(filename, row_index, "name_ordered", item_name)
                break
        else:
            if not btn_links:
                print("the page is empty")
                update_csv_cell(filename, row_index, "name_ordered", "zzzWrong UPC")
            else:
                print('Theres items loaded but all have "Out of Stock" indicated.')
                update_csv_cell(filename, row_index, "is_out_of_stock", "True")
                update_csv_cell(
                    filename, row_index, "out_of_stock_reason", "product_oss"
                )
                print("try clicking on first item")
                await btn_links[0].click()
                print("try ordering")
                item_name = await order_item(page, total_packs, pack_size)
                update_csv_cell(filename, row_index, "name_ordered", item_name)

    except Exception as e:
        print(f"Failed to buy item with UPC {upc}: {e}")
        print("Trying to click on the back button...")
        await page.locator(".dx-icon.dx-icon-arrowleft").click()
        print("Clicked on the back button successfully.")
        update_csv_cell(
            filename, row_index, "name_ordered", "zzFailed to buy"
        )  # Update CSV to indicate failure


async def order_item(page, total_packs, pack_size):
    # Attempt to locate "Case" and "Each" containers
    case_container = page.locator('text="Case"').locator(
        'xpath=ancestor::div[contains(@class, "flex-centered-vertical")][contains(@class, "margin-left-8")]'
    )
    each_container = page.locator('text="Each"').locator(
        'xpath=ancestor::div[contains(@class, "flex-centered-vertical")][contains(@class, "margin-left-8")]'
    )
    case_count = await case_container.count()
    each_count = await each_container.count()
    unit_selector = 'div.value[data-bind="number: orderItem.unitSize"]'
    unit_size_element = page.locator(unit_selector)
    unit_size = await unit_size_element.inner_text()
    unit_size = int(unit_size) if unit_size else 1
    total_units_needed = int(total_packs) * int(pack_size)
    cases_needed = round(total_units_needed / unit_size)
    selector = ".description-header"
    item_text = await page.locator(
        selector
    ).first.inner_text()  # Get text from the first matching element
    print(
        "csv pack_size:",
        pack_size,
        "csv total_packs:",
        total_packs,
        "web unit_size:",
        unit_size,
        "total_units_needed:",
        total_units_needed,
        "cases_needed:",
        cases_needed,
    )
    if case_count > 0 and each_count > 0:
        cases_needed = total_units_needed // unit_size
        each_needed = total_units_needed % unit_size
        print("cases_needed:", cases_needed, "each_needed:", each_needed)

        print(
            f"Setting 'Case' orders to {cases_needed} and 'Each' orders to {each_needed}"
        )
        # Fill in the "Each" quantity
        if each_needed:
            await each_container.locator(".dx-texteditor-input").fill(
                str(max(3, each_needed))
            )
        # Fill in the "Case" quantity
        await case_container.locator(".dx-texteditor-input").fill(str(cases_needed))
        # Check if the element with the specified class name exists
        print("checking for overlay")
        await page.wait_for_timeout(3000)
        overlay_yes_count = await page.locator(
            '.dx-button.dx-button-success.dx-button-mode-contained.dx-widget.button-left-indent.dx-button-has-text.dx-dialog-button >> text="Yes"'
        ).count()
        if overlay_yes_count > 0:
            print('Trying to click on "Yes"')
            await page.locator(
                '.dx-button.dx-button-success.dx-button-mode-contained.dx-widget.button-left-indent.dx-button-has-text.dx-dialog-button >> text="Yes"'
            ).click()
            print("Clicked on 'Yes'.")
        else:
            print("The overlay does not exist.")

        print(
            f"Set 'Case' orders to {cases_needed} and 'Each' orders to {each_needed} successfully."
        )
    else:
        print(
            "Either 'Case' or 'Each' container is not found. Falling back to default method."
        )
        fallback_selector = "div.ordering-input-content > div.flex-centered-vertical.margin-left-8 .dx-texteditor-input"
        await page.locator(fallback_selector).fill(str(cases_needed))
        overlay_exists = (
            await page.locator(
                ".dx-overlay-wrapper.dx-dialog.dx-popup-wrapper.dx-dialog-wrapper.dx-dialog-root.dx-overlay-modal.dx-overlay-shader"
            ).count()
            > 0
        )
        print("overlay_exists", overlay_exists)
        if overlay_exists:
            # If the element exists, click on the div with aria-label="Yes"
            await page.locator(
                '.dx-button.dx-button-success.dx-button-mode-contained.dx-widget.button-left-indent.dx-button-has-text.dx-dialog-button >> text="Yes"'
            ).click()
            print("Clicked on 'Yes'.")
        else:
            print("The overlay does not exist.")
        print("Clicked on the fallback button.")

    # Handle potential modal popup
    try:
        print("Checking for modal popup...")
        modal = await page.wait_for_selector(
            "order-type-select-item", state="visible", timeout=5000
        )
        await modal.locator("div").filter(has_text="Regular Order").first().click()
        await page.get_by_label("OK").click()
        print("Handled modal popup successfully.")
    except Exception as e:
        print(f"Modal did not appear or there was an issue handling it: {e}")

    print("Trying to click on the back button...")
    await page.locator(".dx-icon.dx-icon-arrowleft").click()
    print("Clicked on the back button successfully.")
    return item_text


def read_csv(filename):
    """Read rows from a CSV file into a list of dictionaries."""
    with open(filename, mode="r", newline="") as file:
        reader = csv.DictReader(file)
        return [row for row in reader]


def update_csv_cell(filename, row_index, column_name, new_value):
    """Update a specific cell in a CSV file using column name."""
    # Read the CSV data into a list of dictionaries
    with open(filename, mode="r", newline="") as file:
        reader = csv.DictReader(file)
        data = list(reader)

    # Check if the column name exists
    if column_name not in data[0]:
        print(f"Column '{column_name}' does not exist in the CSV.")
        return

    # Update the specific cell if the row exists
    if 0 <= row_index < len(data):
        data[row_index][column_name] = new_value
    else:
        print(f"Row index '{row_index}' is out of range.")
        return

    # Write the updated data back to the CSV
    with open(filename, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(data)


import csv


def ensure_second_column_name_ordered(filename):
    with open(filename, mode="r", newline="") as file:
        reader = csv.reader(file)
        headers = [
            header.strip() for header in next(reader)
        ]  # Trim whitespace from headers
        data = list(reader)

    print(f"Existing headers: {headers}")
    if len(headers) >= 2:
        print(f"Second header before modification: '{headers[1]}'")
        if headers[1] != "name_ordered":
            headers.insert(1, "name_ordered")
            data = [row[:1] + [""] + row[1:] for row in data]
    else:
        headers.append("name_ordered")
        data = [row + [""] for row in data]

    with open(filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(data)

    print("CSV file updated successfully.")


def sort_csv_by_column(filename, column_name):
    with open(filename, mode="r", newline="") as file:
        reader = csv.DictReader(file)
        data = list(reader)

    # Trim whitespace from column names in data
    trimmed_data = []
    for row in data:
        trimmed_row = {key.strip(): value for key, value in row.items()}
        trimmed_data.append(trimmed_row)

    column_name = column_name.strip()  # Ensure the target column name is also trimmed
    if column_name not in trimmed_data[0]:
        print(f"Column '{column_name}' does not exist in the CSV.")
        return

    sorted_data = sorted(trimmed_data, key=lambda row: row[column_name].lower())
    with open(filename, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(sorted_data)

    print(f"CSV file has been sorted by '{column_name}'.")


def remove_csv_whitespace(filename):
    # Read the CSV data
    with open(filename, mode="r", newline="") as file:
        reader = csv.reader(file)
        headers = [
            header.strip() for header in next(reader)
        ]  # Remove whitespace from headers
        # Remove leading and trailing whitespace from each cell in each row
        data = [[cell.strip() for cell in row] for row in reader]

    # Write the processed data back to the CSV
    with open(filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)  # Write the processed headers
        writer.writerows(data)  # Write the processed data rows

    print("Whitespace removed from CSV file successfully.")


async def run(playwright: Playwright, filename: str, username, password) -> None:
    """Main workflow."""
    print("###########START###################################")
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    page = await login(page, username, password)
    remove_csv_whitespace(filename)
    ensure_second_column_name_ordered(filename)
    sort_csv_by_column(filename, "product_name")
    remove_csv_whitespace(filename)
    upcs = read_csv(filename)
    for row_index, row in enumerate(upcs):
        if row_index >= 51:
            upc = row.get("upc")
            total_packs = row.get("total_packs_ordered")
            pack_size = row.get("pack_size")
            print(
                "trying to order item with upc:",
                upc,
                "total_packs:",
                total_packs,
                "pack_size:",
                pack_size,
            )
            await process_item(page, upc, filename, row_index, total_packs, pack_size)
            await page.wait_for_timeout(1000)
    await context.close()
    await browser.close()


async def main() -> None:
    async with async_playwright() as playwright:
        # Initialize the parser
        parser = argparse.ArgumentParser()

        # Add parameters
        parser.add_argument("-f", type=str)
        parser.add_argument("-u", type=str)
        parser.add_argument("-p", type=str)

        # Parse the arguments
        fileName = parser.parse_args().f
        username = parser.parse_args().u
        password = parser.parse_args().p
        await run(playwright, fileName, username, password)


asyncio.run(main())
