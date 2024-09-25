import httpx
import re
import logging
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaWebPage
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import urllib.parse
from asyncio import Queue

# Replace these values with your own
api_id = 20870301
api_hash = 'ea27e2de02e64bd057473f07031b30f0'
bot_token = '7962279111:AAHZScdqIOLnYp93Ho_cHmh__GQEv9PUmLI'

# Replace with your channel IDs or usernames
source_channel_id = -1001302730016 # Channel to read messages from
target_channel_id = -1002149047543  # Channel to send the final processed message to

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

# Queue for message processing
message_queue = Queue()

async def get_extra_pe_bot_response(url):
    try:
        async with userbot_client.conversation(2015117555) as conv:
            await conv.send_message(url)
            response_message = await conv.get_response()
            return response_message.text
    except Exception as e:
        logger.error(f"Error while getting response from ExtraPeBot: {e}")
        return None

def encode_url(url):
    try:
        return urllib.parse.quote_plus(url).replace("'", "%27").replace('"', "%22")
    except Exception as e:
        logger.error(f"Error while encoding URL {url}: {e}")
        return url

def is_amazon_url(url):
    try:
        # Regex pattern to match various Amazon-related URLs
        amazon_pattern = re.compile(r'(amzn\.to|amzn\.in|amazon\.com|amazon\.(?:co|ca|de|fr|it|jp|es|uk)|amazon\.in)')
        return bool(amazon_pattern.search(url))
    except Exception as e:
        logger.error(f"Error while checking if URL is Amazon: {e}")
        return False


async def get_short_url(long_url):
    try:
        parsed_url = urlparse(long_url)
        # Parse query parameters
        query_params = parse_qs(parsed_url.query)
        # Update the query parameters
        query_params['tag'] = 'sujithraman-21'
        # Rebuild the URL with updated query parameters
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse(parsed_url._replace(query=new_query))
        encoded_url = encode_url(new_url)

        async with httpx.AsyncClient() as clientx:
            try:
                response = await clientx.get(f'https://www.amazon.in/associates/sitestripe/getShortUrl?longUrl={encoded_url}&marketplaceId=44571')
                response.raise_for_status()
                data = response.json()
                return data.get('longUrl', new_url)
            except httpx.HTTPStatusError as http_err:
                logger.error(f"HTTP error occurred: {http_err}")
            except httpx.RequestError as req_err:
                logger.error(f"Request error occurred: {req_err}")
    except Exception as e:
        logger.error(f"Error while getting short URL for {long_url}: {e}")
    return new_url

async def process_message(event):
    try:
        original_message = event.message
        message = original_message.message
        media = original_message.media
        urls = []
        url_pattern = re.compile(r'https?://[^\s]+')
        urls = url_pattern.findall(message)
        # Filter Amazon URLs
        amazon_urls = [url for url in urls if is_amazon_url(url)]
        if len(amazon_urls) > 15:
            await event.delete()
            logger.info(f"Message deleted due to excessive Amazon URLs: {event.message.id}")
            return

        for url in urls:
            try:
                parsed_url = httpx.URL(url)
                domain = parsed_url.host

                if domain in ['fkrt.cc', 'fkrt.to','fas.st','cutt.ly','extp.in','myntr.in','mynt.ro','fkrt.it']:
                    extra_pe_bot_response = await get_extra_pe_bot_response(url)
                    if extra_pe_bot_response:
                        message = message.replace(url, f'<a href="{extra_pe_bot_response}">🛒 Buy Now</a>')
                    continue
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    try:
                        # Follow redirects and get the final URL
                        response = await client.get(url)
                        final_url = response.url
                        # Check if the final URL is an Amazon URL
                        if is_amazon_url(str(final_url)):
                            # Process Amazon URL
                            short_url = await get_short_url(str(final_url))
                            if short_url:
                                message = message.replace(url, f'<a href="{short_url}">🛒 Buy Now</a>')
                        else:
                            # For non-Amazon URLs, get response from ExtraPeBot
                            extra_pe_bot_response = await get_extra_pe_bot_response(str(final_url))
                            if extra_pe_bot_response:
                                message = message.replace(url, f'<a href="{extra_pe_bot_response}">🛒 Buy Now</a>')

                    except httpx.HTTPStatusError as http_err:
                        logger.error(f"HTTP error occurred while processing URL {url}: {http_err}")
                    except httpx.RequestError as req_err:
                        logger.error(f"Request error occurred while processing URL {url}: {req_err}")

            except Exception as e:
                logger.error(f"Error while processing URL {url}: {e}")

        bold_message = f'<b>{message}</b>'
        
        # Send the processed message to the target channel
        await bot_client.send_message(target_channel_id, bold_message, parse_mode='html')

        # Handle media (optional)
        if isinstance(media, MessageMediaWebPage):
            # Extract URL from the web page media
            webpage_url = media.webpage.url if media.webpage else 'No URL found'
            await bot_client.send_message(target_channel_id, bold_message, parse_mode='html')
        elif media:
            # Handle file media (photos, documents, etc.)
            await bot_client.send_message(target_channel_id, bold_message, parse_mode='html', file=media)

    except Exception as e:
        logger.error(f"Error while processing message {event.message.id}: {e}")


@bot_client.on(events.NewMessage(chats=source_channel_id))
async def handler(event):
    if event:
        try:
            await message_queue.put(event)
        except Exception as e:
            logger.error(f"Error while adding message to queue: {e}")

async def message_processor():
    while True:
        try:
            event = await message_queue.get()
            await process_message(event)
        except Exception as e:
            logger.error(f"Error while processing message from queue: {e}")
        finally:
            message_queue.task_done()

# Start the background task for processing messages
bot_client.loop.create_task(message_processor())

# Run the clients
logger.info("Starting bot clients")
try:
    bot_client.start()
    userbot_client.start()
    bot_client.run_until_disconnected()
except Exception as e:
    logger.error(f"Error while running bot clients: {e}")
