"""
Exceptions customizadas da aplicação.

Hierarquia:
    AppException (base)
    ├── AuthenticationError (401)
    ├── AuthorizationError (403)
    ├── NotFoundError (404)
    ├── ConflictError (409)
    ├── ValidationError (422)
    ├── ExternalServiceError (502)
    └── RateLimitError (429)

Uso:
    raise UserNotFoundError(user_id=123)
    raise InvalidTokenError()
    raise WhatsAppServiceError(detail="timeout")
"""


class AppException(Exception):
    """
    Classe base para todas as exceptions da aplicação.

    Toda exception customizada herda daqui.
    Isso permite capturar qualquer erro do sistema com:
        except AppException as e:
    """

    status_code: int = 500
    detail: str = "Erro interno do servidor"

    def __init__(self, detail: str | None = None, **kwargs):
        self.detail = detail or self.__class__.detail
        self.context = kwargs  # informações extras para logs
        super().__init__(self.detail)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(detail={self.detail!r})"


# ============================================
# 🔐 AUTENTICAÇÃO E AUTORIZAÇÃO (401, 403)
# ============================================


class AuthenticationError(AppException):
    """Usuário não autenticado — token ausente ou inválido."""

    status_code = 401
    detail = "Autenticação necessária"


class InvalidTokenError(AuthenticationError):
    """Token JWT inválido ou malformado."""

    detail = "Token inválido"


class ExpiredTokenError(AuthenticationError):
    """Token JWT expirado."""

    detail = "Token expirado. Faça login novamente"


class InvalidCredentialsError(AuthenticationError):
    """Email ou senha incorretos."""

    detail = "Email ou senha incorretos"


class AuthorizationError(AppException):
    """Usuário autenticado mas sem permissão para a ação."""

    status_code = 403
    detail = "Sem permissão para realizar esta ação"


# ============================================
# 🔍 NÃO ENCONTRADO (404)
# ============================================


class NotFoundError(AppException):
    """Recurso não encontrado."""

    status_code = 404
    detail = "Recurso não encontrado"


class UserNotFoundError(NotFoundError):
    """Usuário específico não encontrado."""

    detail = "Usuário não encontrado"

    def __init__(self, user_id: int | str | None = None):
        detail = f"Usuário {user_id} não encontrado" if user_id else self.detail
        super().__init__(detail=detail, user_id=user_id)


class TransactionNotFoundError(NotFoundError):
    """Transação financeira não encontrada."""

    detail = "Transação não encontrada"

    def __init__(self, transaction_id: int | str | None = None):
        detail = (
            f"Transação {transaction_id} não encontrada"
            if transaction_id
            else self.detail
        )
        super().__init__(detail=detail, transaction_id=transaction_id)


# ============================================
# ⚡ CONFLITO (409)
# ============================================


class ConflictError(AppException):
    """Conflito com estado atual do recurso."""

    status_code = 409
    detail = "Conflito com recurso existente"


class EmailAlreadyExistsError(ConflictError):
    """Email já cadastrado no sistema."""

    detail = "Este email já está em uso"

    def __init__(self, email: str | None = None):
        detail = f"O email {email} já está em uso" if email else self.detail
        super().__init__(detail=detail, email=email)


# ============================================
# ✅ VALIDAÇÃO (422)
# ============================================


class ValidationError(AppException):
    """Dados de entrada inválidos."""

    status_code = 422
    detail = "Dados inválidos"


class InvalidAmountError(ValidationError):
    """Valor monetário inválido."""

    detail = "Valor deve ser maior que zero"


class InvalidDateRangeError(ValidationError):
    """Período de datas inválido."""

    detail = "Data inicial deve ser anterior à data final"


# ============================================
# 🌐 SERVIÇOS EXTERNOS (502)
# ============================================


class ExternalServiceError(AppException):
    """Erro ao comunicar com serviço externo."""

    status_code = 502
    detail = "Erro ao comunicar com serviço externo"


class AIServiceError(ExternalServiceError):
    """Erro no serviço de Inteligência Artificial."""

    detail = "Serviço de IA temporariamente indisponível"


class WhatsAppServiceError(ExternalServiceError):
    """Erro no serviço do WhatsApp."""

    detail = "Serviço do WhatsApp temporariamente indisponível"


class AudioServiceError(ExternalServiceError):
    """Erro no serviço de processamento de áudio."""

    detail = "Serviço de áudio temporariamente indisponível"


class StorageServiceError(ExternalServiceError):
    """Erro no serviço de armazenamento de arquivos."""

    detail = "Serviço de armazenamento temporariamente indisponível"


# ============================================
# 🚦 RATE LIMIT (429)
# ============================================


class RateLimitError(AppException):
    """Muitas requisições em um curto período."""

    status_code = 429
    detail = "Muitas requisições. Tente novamente em alguns instantes"
