from app.llm.gateway import GenerationRequest, LLMGateway


def test_gateway_local_fallback_generates_text():
    gateway = LLMGateway()
    text = gateway.generate(GenerationRequest(prompt="Student: Explain gravity"))
    assert text

