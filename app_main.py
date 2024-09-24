import httpx
from telethon import TelegramClient, events
import logging
import asyncio
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import urllib.parse

# Replace these values with your own
api_id = 20870301
api_hash = 'ea27e2de02e64bd057473f07031b30f0'
bot_token = '7265352270:AAFmhjFRwKfL8Eu8DJoQQ9AL7YrOamgVhx0'

# Configure logging
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Initialize the Telethon client for the bot
bot_client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

# Initialize the Telethon client for the userbot
userbot_client = TelegramClient('userbot', api_id, api_hash)

# Replace with your channel IDs or usernames
source_channel_id = 'source_channel_id'  # Channel to read messages from
target_channel_id = 'target_channel_id'  # Channel to send the final processed message to

def encode_url(url):
    try:
        return urllib.parse.quote_plus(url).replace("'", "%27").replace('"', "%22")
    except Exception as e:
        logger.error(f"Error while encoding URL {url}: {e}")
        return url

def is_amazon_url(url):
    try:
        return "amazon.in" in url
    except Exception as e:
        logger.error(f"Error while checking if URL is Amazon: {e}")
        return False

def get_short_url(long_url):
    try:
        # Parse the URL
        parsed_url = urlparse(long_url)

        # Parse query parameters
        query_params = parse_qs(parsed_url.query)

        # Update the query parameters
        query_params['tag'] = 'sujithraman-21'

        # Rebuild the URL with updated query parameters
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse(parsed_url._replace(query=new_query))
        encoded_url = encode_url(new_url)

        # Get the short URL from Amazon API
        response = httpx.get(f'https://www.amazon.in/associates/sitestripe/getShortUrl?longUrl={encoded_url}&marketplaceId=44571')
        if response:
            data = response.json()
            return data.get('longUrl', None)
    except Exception as e:
        logger.error(f"Error while getting short URL for {long_url}: {e}")
    return None

async def get_extra_pe_bot_response(url):
    try:
        # Send the message to the ExtraPeBot (replace with correct bot ID)
        await userbot_client.send_message(2015117555, url)
        messages = await userbot_client.get_messages(2015117555, limit=1)
        if messages:
            return messages[0].text
    except Exception as e:
        logger.error(f"Error while getting response from ExtraPeBot: {e}")
        return None

async def process_message(message):
    try:
        urls = []

        # Extract URLs from the message
        url_pattern = re.compile(r'https?://[^\s]+')
        urls = url_pattern.findall(message)

        # Process URLs and replace with short or ExtraPeBot responses
        for url in urls:
            try:
                response = httpx.get(url, follow_redirects=True)
                if is_amazon_url(str(response.url)):
                    short_url = get_short_url(str(response.url))
                    if short_url:
                        message = message.replace(url, f'<a href="{short_url}">🛒 Buy Now</a>')
                else:
                    extra_pe_bot_response = await get_extra_pe_bot_response(url)
                    if extra_pe_bot_response:
                        message = message.replace(url, f'<a href="{extra_pe_bot_response}">🛒 Buy Now </a>')
            except Exception as e:
                logger.error(f"Error while processing URL {url}: {e}")

        # Return the fully processed message
        return message

    except Exception as e:
        logger.error(f"Error while processing message: {e}")
        return None

async def forward_processed_message():
    try:
        # Get the latest message from the source channel
        messages = await userbot_client.get_messages(source_channel_id, limit=1)

        if messages:
            original_message = messages[0].message
            logger.info(f"Original message: {original_message}")

            # Process the message
            processed_message = await process_message(original_message)

            if processed_message:
                # Send the processed message to the target channel
                await userbot_client.send_message(target_channel_id, processed_message, parse_mode='html')

                logger.info(f"Processed and forwarded message: {processed_message}")
            else:
                logger.info("No message to forward after processing.")
        else:
            logger.info("No new messages to process.")

    except Exception as e:
        logger.error(f"Error while forwarding processed message: {e}")

async def message_monitor():
    while True:
        await forward_processed_message()
        # Wait for a few seconds before checking again (adjust as needed)
        await asyncio.sleep(10)

async def main():
    # Start the userbot and bot clients
    await userbot_client.start()
    await bot_client.start()

    # Run the message monitor in the background
    bot_client.loop.create_task(message_monitor())

    # Keep the bot running
    await bot_client.run_until_disconnected()

# Run the clients
logger.info("Starting bot clients")
try:
    userbot_client.loop.run_until_complete(main())
except Exception as e:
    logger.error(f"Error while running bot clients: {e}")
