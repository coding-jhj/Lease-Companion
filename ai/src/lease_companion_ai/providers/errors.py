"""외부 provider 오류를 민감 입력 없이 전달하는 공통 예외."""


class ProviderError(RuntimeError):
    """호출부가 제공자 SDK 예외와 입력 원문에 의존하지 않게 하는 오류."""


class ProviderUnavailableError(ProviderError):
    """키·SDK·설정 부재로 provider를 호출할 수 없음."""


class ProviderQuotaError(ProviderError):
    """호출량·비용·할당량 제한으로 provider를 호출할 수 없음."""


class ProviderResponseValidationError(ProviderError):
    """provider 응답이 고정 계약 검증을 통과하지 못함."""
