"""Wrapper around IBM GENAI APIs for use in Langchain"""
import logging
from typing import Any, Iterator, List, Mapping, Optional

from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.schema.output import GenerationChunk
from pydantic import BaseModel, Extra

try:
    from langchain.llms.base import LLM
    from langchain.llms.utils import enforce_stop_tokens
except ImportError:
    raise ImportError("Could not import langchain: Please install ibm-generative-ai[langchain] extension.")

from genai import Credentials, Model
from genai.schemas import GenerateParams

logger = logging.getLogger(__name__)

__all__ = ["LangChainInterface"]


class LangChainInterface(LLM, BaseModel):
    """
    Wrapper around IBM GENAI models.
    To use, you should have the ``genai`` python package installed
    and initialize the credentials attribute of this class with
    an instance of ``genai.Credentials``. Model specific parameters
    can be passed through to the constructor using the ``params``
    parameter, which is an instance of GenerateParams.
    Example:
        .. code-block:: python
            llm = LangChainInterface(model="google/flan-ul2", credentials=creds)
    """

    credentials: Credentials = None
    model: Optional[str] = None
    params: Optional[GenerateParams] = None

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        _params = self.params or GenerateParams()
        return {
            **{"model": self.model},
            **{"params": _params},
        }

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "IBM GENAI"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call the IBM GENAI's inference endpoint.
        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.
            run_manager: Optional callback manager.
        Returns:
            The string generated by the model.
        Example:
            .. code-block:: python
                llm = LangChainInterface(model_id="google/flan-ul2", credentials=creds)
                response = llm("What is a molecule")
        """
        params = self.params or GenerateParams()
        params.stop_sequences = stop or params.stop_sequences
        if params.stream:
            final_text = ""
            for chunk in self._stream(prompt=prompt, stop=stop, run_manager=run_manager, **kwargs):
                final_text += chunk.text
            if stop is not None:
                final_text = enforce_stop_tokens(final_text, stop)
            return final_text

        model = Model(model=self.model, params=params, credentials=self.credentials)
        text = model.generate(prompts=[prompt], **kwargs)[0].generated_text
        logger.info("Output of GENAI call: {}".format(text))
        if params.stop_sequences is not None:
            text = enforce_stop_tokens(text, params.stop_sequences)
        return text

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        """Call the IBM GENAI's inference endpoint which then streams the response.
        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.
            run_manager: Optional callback manager.
        Returns:
            The iterator which yields generation chunks.
        Example:
            .. code-block:: python
                llm = LangChainInterface(model_id="google/flan-ul2", credentials=creds)
                for chunk in llm.stream("What is a molecule?"):
                    print(chunk.text)
        """
        params = self.params or GenerateParams()
        params.stop_sequences = stop or params.stop_sequences

        model = Model(model=self.model, params=params, credentials=self.credentials)
        for response in model.generate_stream(prompts=[prompt], **kwargs):
            logger.info("Chunk received: {}".format(response.generated_text))
            yield GenerationChunk(text=response.generated_text, generation_info=response.dict())
            if run_manager:
                run_manager.on_llm_new_token(token=response.generated_text, response=response)
