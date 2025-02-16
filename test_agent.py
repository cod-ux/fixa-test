from fixa import Test, Agent, Scenario, Evaluation, TestRunner
from fixa.evaluators import LocalEvaluator
from dotenv import load_dotenv
import ngrok, os, asyncio
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv(override=True)

# Debug: Print all relevant environment variables
logger.debug("Environment Variables Check:")
logger.debug(f"OpenAI API Key length: {len(os.getenv('OPENAI_API_KEY', ''))} chars")
logger.debug(f"Model: {os.getenv('MODEL', 'Not set')}")
logger.debug(f"Deepgram API Key length: {len(os.getenv('DEEPGRAM_API_KEY', ''))} chars")
logger.debug(f"Cartesia API Key length: {len(os.getenv('CARTESIA_API_KEY', ''))} chars")
logger.debug(f"Twilio Account SID: {os.getenv('TWILIO_ACCOUNT_SID')}")
logger.debug(
    f"Twilio Auth Token length: {len(os.getenv('TWILIO_AUTH_TOKEN', ''))} chars"
)
logger.debug(f"Ngrok Auth Token length: {len(os.getenv('NGROK_AUTH_TOKEN', ''))} chars")

TWILIO_PHONE_NUMBER = "+16024973768"  # the twilio phone number to initiate calls from
PHONE_NUMBER_TO_CALL = "+447436962389"  # the phone number to call


async def main():
    # Create an agent named "jessica"
    agent = Agent(
        name="jessica",
        prompt="pretend that you are a young woman named jessica who says 'like' a lot",
        voice_id="79a125e8-cd45-4c13-8a67-188112f4dd22",  # Add voice_id here
    )
    logger.info(f"Created agent: {agent.name} with voice_id: {agent.voice_id}")

    # Create a test scenario
    scenario = Scenario(
        name="order_donut",
        prompt="You are going to call a coffee shop to order something for you. order a dozen donuts with sprinkles and a coffee to the coffee shop you called",
        evaluations=[
            Evaluation(name="order_success", prompt="the order was successful"),
            Evaluation(
                name="price_confirmed",
                prompt="the agent confirmed the price of the order",
            ),
        ],
    )
    logger.info(f"Created scenario: {scenario.name} with prompt: {scenario.prompt}")

    # start an ngrok server so twilio can access your local websocket endpoint
    port = 8765
    listener = await ngrok.forward(port, authtoken=os.getenv("NGROK_AUTH_TOKEN"))  # type: ignore
    ngrok_url = listener.url()
    logger.info(f"Starting test with ngrok URL: {ngrok_url}")
    logger.info(f"WebSocket URL will be: wss://{ngrok_url.replace('https://', '')}/ws")

    # initialize test runner with ngrok configuration
    test_runner = TestRunner(
        port=port,
        ngrok_url=listener.url(),
        twilio_phone_number=TWILIO_PHONE_NUMBER,
        evaluator=LocalEvaluator(model="gpt-4o"),
    )
    logger.debug("TestRunner initialized with ngrok configuration")

    # Create and add test
    test = Test(scenario=scenario, agent=agent)
    test_runner.add_test(test)
    logger.debug("Test added to runner")

    try:
        test_results = await test_runner.run_tests(
            phone_number=PHONE_NUMBER_TO_CALL,
            type=TestRunner.OUTBOUND,
        )
        logger.debug(f"Test completed with results: {test_results}")
        print("\n✨ Test Results:")
        print(test_results)
    except Exception as e:
        logger.error(f"Error running test: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
