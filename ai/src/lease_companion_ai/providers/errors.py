"""외부 provider 오류를 민감 입력 없이 전달하는 공통 예외."""


class ProviderError(RuntimeError):
    """호출부가 제공자 SDK 예외와 입력 원문에 의존하지 않게 하는 오류."""
