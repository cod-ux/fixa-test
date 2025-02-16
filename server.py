from flask import Flask, request, jsonify
from fixa import Test, Agent, Scenario, Evaluation, TestRunner
from fixa.evaluators import LocalEvaluator
from dotenv import load_dotenv
import ngrok, os, asyncio
import logging
from typing import List, Dict, Any
from dataclasses import dataclass
from pydantic import BaseModel

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

# Constants
TWILIO_PHONE_NUMBER = "+16024973768"  # the twilio phone number to initiate calls from

app = Flask(__name__)


class EvaluationRequest(BaseModel):
    name: str
    prompt: str


class ScenarioRequest(BaseModel):
    name: str
    prompt: str
    evaluations: List[EvaluationRequest]


class AgentRequest(BaseModel):
    name: str
    prompt: str


class TestRequest(BaseModel):
    phone_number: str
    agent: AgentRequest
    scenario: ScenarioRequest


async def run_test(data: Dict[str, Any]):
    # Create agent
    agent = Agent(name=data["agent"]["name"], prompt=data["agent"]["prompt"])
    logger.info(f"Created agent: {agent.name}")

    # Create evaluations
    evaluations = [
        Evaluation(name=e["name"], prompt=e["prompt"])
        for e in data["scenario"]["evaluations"]
    ]

    # Create scenario
    scenario = Scenario(
        name=data["scenario"]["name"],
        prompt=data["scenario"]["prompt"],
        evaluations=evaluations,
    )
    logger.info(f"Created scenario: {scenario.name}")

    # Start ngrok tunnel
    port = 8765
    listener = await ngrok.forward(port, authtoken=os.getenv("NGROK_AUTH_TOKEN"))
    ngrok_url = listener.url()
    logger.info(f"Starting test with ngrok URL: {ngrok_url}")

    # Initialize test runner
    test_runner = TestRunner(
        port=port,
        ngrok_url=ngrok_url,
        twilio_phone_number=TWILIO_PHONE_NUMBER,
        evaluator=LocalEvaluator(),
    )
    logger.debug("TestRunner initialized with ngrok configuration")

    # Create and add test
    test = Test(scenario=scenario, agent=agent)
    test_runner.add_test(test)
    logger.debug("Test added to runner")

    try:
        test_results = await test_runner.run_tests(
            phone_number=data["phone_number"],
            type=TestRunner.OUTBOUND,
        )
        logger.debug(f"Test completed with results: {test_results}")
        return test_results
    except Exception as e:
        logger.error(f"Error running test: {str(e)}")
        raise e


@app.route("/test", methods=["POST"])
def create_test():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate required fields
        required_fields = {
            "phone_number": str,
            "agent": {"name": str, "prompt": str},
            "scenario": {"name": str, "prompt": str, "evaluations": list},
        }

        def validate_fields(data_dict, required):
            for field, field_type in required.items():
                if field not in data_dict:
                    return False, f"Missing required field: {field}"
                if isinstance(field_type, dict):
                    if not isinstance(data_dict[field], dict):
                        return False, f"Field {field} must be an object"
                    valid, error = validate_fields(data_dict[field], field_type)
                    if not valid:
                        return False, error
                elif not isinstance(data_dict[field], field_type):
                    return False, f"Field {field} must be of type {field_type.__name__}"
            return True, None

        valid, error = validate_fields(data, required_fields)
        if not valid:
            return jsonify({"error": error}), 400

        # Run the test asynchronously
        result = asyncio.run(run_test(data))
        return jsonify({"result": str(result)}), 200

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7821, debug=True)
