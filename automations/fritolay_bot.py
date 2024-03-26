import asyncio
from web_agent import JoshyTrain
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
from utils.json_utils import extract_json
from utils.csv_utils import read_from_csv, write_to_csv
import argparse
from openai import OpenAI
import re

load_dotenv()

port = os.getenv("PORT")
model = OpenAI()
model.timeout = 30

async def chat(prompt):
    print("User:", prompt)
    response = model.chat.completions.create(
        model="gpt-4-0125-preview",
        messages=[
            {
                "role": "user",
                "content": prompt,
            },
        ],
        max_tokens=4096,
    )
    message = response.choices[0].message
    message_text = message.content
    print("Assistant:", message_text)
    return message_text


async def search(page, item_name, search_terms):
    try:
        joshyTrain = JoshyTrain(page)
        minimum_confidence = 7
        maximum_search_terms = 7
        while True:
            try:
                response = await chat(
                    f"""
                come up with different search terms for {item_name}
                for example: 
                Use your knowledge of the product to come up with different search terms. (For example Sun Chips is a typo of SunChips)
                if the full name is Cheetos Crunchy - Cheddar Jalapeno - 3.25 oz, you can try the following
                - Cheetos Crunchy Cheddar Jalapeno (brand + product name + flavor)
                - Cheetos Crunchy (brand + product name)
                - Cheddar Jalapeno (flavor)
                - Cheetos (brand)

                FOLLOW THE PATTERNS OF THE EXAMPLES ABOVE BEFORE YOU TRY TO COME UP WITH YOUR OWN SEARCH TERMS
                DON"T TRY YOUR OWN SEARCH TERMS UNTIL YOU HAVE TRIED THE PATTERNS ABOVE
                DON'T include the size in the search terms you come up with
                DON'T repeat search terms

                Just come up with ONE search term

                you have already tried {search_terms}

                ONLY respond in the following JSON format:

                {{"combination logic": "brand + product name + flavor" / "brand + product name" / "flavor" / "brand" / "your own search term", "searchTerm": "your search term"}}
                """
                )
                # the search term is appended into a list that is passed into gpt so that it knows to not repeat search terms
                data = extract_json(response)
                if data and "searchTerm" in data:
                    search_term = data["searchTerm"]
                    search_terms.append(data)

                    # Manual Search
                    await page.get_by_placeholder("Search Product").fill(search_term)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(5000)
                    await page.screenshot(path="screenshot.jpg", full_page=True)

                    # Check for the element
                    no_record_element = await page.query_selector(
                        'h1:text("No Record Found")'
                    )

                    # Validate if the element exists
                    if no_record_element:
                        if len(search_terms) > maximum_search_terms:
                            return 0
                        continue
                    else:
                        break
                else:
                    return 0
            except Exception as e:
                print(e)
                continue

        # return 2

        # loop through every product on the page and get its full name
        card_text_map = {}
        card_titles = await page.query_selector_all(".pro-list-title-mob")
        for index, card_title in enumerate(card_titles):
            await card_title.click()
            await page.wait_for_selector(".product-title", state="visible")
            modal_text = await page.inner_text(".product-title")
            card_text_map[index + 2] = modal_text
            await page.click('[aria-label="close"]')
            await page.wait_for_timeout(
                2000
            )  # Wait for the modal to close, adjust as needed

        if len(card_text_map) == 0:
            if len(search_terms) <= maximum_search_terms:
                return await search(page, item_name, search_terms)
            else:
                return 0

        # gpt finds cloest product with name
        try:
            prompt = f"""
            given the python dict, please return the key where the value of this key is closest to {item_name} in the {card_text_map}. 

            give your confidence level on this from 0-10, which is your combined score from the following criteria:

    the product name:
    - 3pts if the product name is exactly correct 
    - 2pts if the product name is close to the correct product name, for example, if the item name is Cheetos Crunchy - Cheddar Jalapeno - 3.25 oz, then Cheetos is close to the correct product name (Cheetos Crunchy is the correct product name)
    - 1pt if the product name is somewhat close to the correct product name
    - 0pt if the product name is not close to the correct product name

    the flavor:
    - 3pts if the flavor is exactly correct 
    - 2pts if the flavor is close to the correct flavor, for example, if the item name is Cheetos Crunchy - Cheddar Jalapeno - 3.25 oz, then Jalapeno is close to the correct flavor (Cheddar Jalapeno is the correct flavor), only having Cheedar is not close to the correct flavor because the entire line of snacks is cheese flavored
    - 1pt if the flavor is somewhat close to the correct flavor
    - 0pt if the flavor is not close to the correct flavor

    the size:
    - 4pts if the size is exactly correct 
    - 3pts if the size is close to the correct size, if the size difference is within 0.5 oz
    - 2pt if the size is somewhat close to the correct size, if the size difference is within 1 oz
    - 1pt if the size is somewhat close to the correct size, if the size difference is within 2 oz
    - 0pt if the size is not close to the correct size

    Add the score up and ONLY return the following JSON format:
    {{
    "key": "the key of the item that matches {item_name}",
    "reasoning": "your reasoning",
    "confidence": "your combined confidence level",
    }}

    have your explanation inside the JSON, your response should only contain the JSON and NOTHING ELSE
    """
            response = await chat(prompt)
            data = extract_json(response)
            confidence = int(data["confidence"])
            i = int(data["key"])
            item_div = await page.query_selector(
                f".MuiGrid-root-128.product-tile.MuiGrid-item-130.MuiGrid-grid-xs-6-168.MuiGrid-grid-sm-4-180.MuiGrid-grid-md-4-194.MuiGrid-grid-lg-3-207:nth-of-type({i}) .productlist-img"
            )
            await item_div.click()
            try:
                prompt = f"""Are these two the same item? {item_name} and {card_text_map[i]}, little difference in size by 1oz or smaller is okay. DO NOT CLICK OR INTERACT WITH ANYTHING ON THE PAGE. Respond with the following JSON format: {{"answer": "true or false", "reasoning": "your reasoning"}}"""
                response = await joshyTrain.chat(prompt)
            except Exception as e:
                print(e)
            close_icon = await page.query_selector(
                'img[src="a8d398bb099ac1e54d401925030b9aa2.svg"]'
            )
            await close_icon.click()
            data = extract_json(response)
            if data["answer"] == "true":
                await page.screenshot(path="screenshot.jpg", full_page=True)
                # continue searching if confidence did not meet criteria
                if confidence >= minimum_confidence:
                    return i
            if len(search_terms) < maximum_search_terms:
                return await search(page, item_name, search_terms)
            else:
                return 0
        except Exception as e:
            if len(search_terms) < maximum_search_terms:
                return await search(page, item_name, search_terms)
            else:
                return 0
    except Exception as e:
        print(e)
        return 0


async def main():
    async with async_playwright() as p:
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

        # fileName = "./fritolay.csv"
        # username = "klaus@duffl.com"
        # password = "Garkbock33"

        print(fileName, username, password)

        browser = await p.chromium.launch(headless=False, slow_mo=50)

        page = await browser.new_page()
        joshyTrain = JoshyTrain(page)
        ## LOGGING IN
        await page.goto("https://shop.fls2u.com/login")
        await page.wait_for_timeout(5000)
        await page.get_by_text("Accept All Cookies", exact=True).click()
        await page.get_by_label("Username / Email*").click()
        await page.get_by_label("Username / Email*").fill(username)
        await page.get_by_label("Password*").click()
        await page.get_by_label("Password*").fill(password)
        await page.get_by_label("login", exact=True).click()
        await page.wait_for_timeout(5000)
        response= await joshyTrain.chat("""Is the login successful? The login is ONLY failed if the page SPECIFICALLY shows that the login has failed. Respond in the following JSON format: {"login": "true or false"}""")
        data = extract_json(response)
        if data["login"] == "false":
            await page.screenshot(path="screenshot.jpg", full_page=True)
            raise Exception("Incorrect login credentials")

        rows = read_from_csv(fileName)
        for row in rows:
            row["name_ordered"] = ""
            item_name = row["product_name"]
            # item_name = "Sun Chips - French Onion - 7.0 oz"

            # search function returns index of "found" item, index starts from 1
            i = await search(page, item_name, [])
            print(i)

            if not i:
                print("not_found")
                row["is_out_of_stock"] = True
                row["out_of_stock_reason"] = "not_found"
                continue

            try:
                # find the image of the item card (you can only open pop up from image or title)
                item_div = await page.query_selector(
                    f".MuiGrid-root-128.product-tile.MuiGrid-item-130.MuiGrid-grid-xs-6-168.MuiGrid-grid-sm-4-180.MuiGrid-grid-md-4-194.MuiGrid-grid-lg-3-207:nth-of-type({i}) .productlist-img"
                )

                print(item_div)

                await item_div.click()

                await page.wait_for_timeout(2000)
                await page.screenshot(path="screenshot.jpg", full_page=True)

                await page.wait_for_selector(".product-title", state="visible")
                modal_text = await page.inner_text(".product-title")
                row["name_ordered"] = modal_text

                # get the product details div and get upc and price
                product_details_div = await page.query_selector(
                    ".MuiGrid-root-128.product-detail-wrapper-inner"
                )

                ## probably dont need this right now
                # upc_number = await product_details_div.query_selector(
                #     '.product-info-text:has-text("UPC:")'
                # )
                # upc_number = re.search(r"UPC:\s*(\d+)", await upc_number.inner_text())
                # if upc_number:
                #     upc_number = upc_number.group(1)
                #     if upc_number != row["upc"]:
                #         row["updated_upc"] = upc_number

                product_cost = await product_details_div.query_selector(".product-cost")
                product_cost = re.search(r"Cost:\s*\$(\d+\.\d+)", await product_cost.inner_text())
                if product_cost:
                    product_cost = product_cost.group(1)
                    if product_cost != row["pack_price"]:
                        row["updated_price"] = product_cost

                # check if its out of stock
                out_of_stock = await page.query_selector(".product-out-stock.list")
                if out_of_stock:
                    print("product_oos")
                    row["is_out_of_stock"] = True
                    row["out_of_stock_reason"] = "product_oos"
                else:
                    # order the item
                    input_element = await page.query_selector(
                        ".product-detail-wrapper .MuiInputBase-input-395.MuiOutlinedInput-input-382.MuiInputBase-inputAdornedEnd-400.MuiOutlinedInput-inputAdornedEnd-386"
                    )
                    print(input_element)
                    number_of_packs = row["total_packs_ordered"]
                    await input_element.fill(number_of_packs)
                    await page.keyboard.press("Tab")

                    await page.wait_for_timeout(2000)
                    await page.screenshot(path="screenshot.jpg", full_page=True)

                # close the details pop up
                close_icon = await page.query_selector(
                    'img[src="a8d398bb099ac1e54d401925030b9aa2.svg"]'
                )
                await close_icon.click()
            except Exception as e:
                print(e)
                row["out_of_stock_reason"] = "not_found"

            await page.wait_for_timeout(2000)
            await page.screenshot(path="screenshot.jpg", full_page=True)
            print(row)

        # opening up cart
        try:
            cart_icon = await page.query_selector('img[src="www/images/cart.svg"]')
            await cart_icon.click()

            await page.screenshot(path="screenshot.jpg", full_page=True)
        except Exception as e:
            print(e)

        fileName = "./results/" + fileName.split("/")[1] + ".csv"
        # writing csv with new columns
        write_to_csv(rows, fileName)


asyncio.run(main())
