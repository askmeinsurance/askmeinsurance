from deepeval.synthesizer import Synthesizer, Evolution
from deepeval.synthesizer.config import StylingConfig, EvolutionConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from deepeval.models import DeepEvalBaseLLM

from dotenv import load_dotenv
import json
import os
from pathlib import Path
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path, override=True)

MODEL_NAME = "gemini-2.5-flash-lite"


expected_output_format = (
    "A highly structured, professional, and compliant response that satisfies the following strict criteria:\n\n"
    "1. TONE & BEHAVIORAL PRINCIPLES:\n"
    "- Comprehensiveness: Covers the full picture. Must include what a concept/product is, how it works, what it covers, "
    "AND what it does NOT cover (proactively surfacing exclusions, waiting periods, and claim conditions). Includes relevant "
    "regulatory/tax dimensions (e.g., CPF, MediShield Life, SRS) and anticipates logical follow-up questions.\n"
    "- Diversity: Presents 2-3 distinct approaches, product archetypes, or trade-offs (e.g., term vs. whole life). Explains "
    "who each option suits based on life stages, risk appetites, and financial goals.\n"
    "- Empowerment: Explains the 'why' behind trade-offs. Formally defines jargon in parentheses immediately after first use "
    "[e.g., sum assured (the total amount the insurer pays out upon a claim)]. Provides an actionable mental framework/decision rule. "
    "Ends with 1-2 reflective questions to help the user evaluate their own priorities.\n\n"
    "2. STRICT GROUNDING & EVIDENCE:\n"
    "- Based exclusively on provided evidence (no external facts, figures, or guessing). If data is missing, it must explicitly "
    "state: 'The retrieved documents don't include details on [X] — you'd want to confirm this directly with the insurer or your advisor.'\n\n"
    "3. FORMATTING CONSTRAINTS:\n"
    "- Uses the most appropriate layout: Prose (for concepts), Bullet/Numbered lists (for features/steps), or Markdown Tables "
    "(for comparisons across shared dimensions, max 4 columns with header row).\n"
    "- Strictly maximum of TWO format types per response (e.g., prose + one table).\n"
    "- Bullet points must be single-idea only (no paragraph bullets). Uses Markdown headers (###) only if the response covers "
    "3+ distinct topics and is over 150 words. Uses bolding strictly for key terms on first use or critical caveats."
)


styling_config = StylingConfig(
    input_format="Inquiries, FAQs, and objections from potential insurance buyers, ranging from casual to highly specific.",
    expected_output_format=expected_output_format,
    task="Explaining core insurance principles, policy mechanics, and product differences to prospects to build trust and aid a sales decision.",
    scenario=(
        "A user is shopping for insurance and asks a specific technical or practical question, "
        "such as 'What is the difference between a co-pay and a co-insurance?' or 'Why do I need a life insurance policy right now?'"
    ),
)


class GeminiDeepEvalLLM(DeepEvalBaseLLM):
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
            temperature=0,
        )

    def load_model(self) -> "GeminiDeepEvalLLM":
        return self

    def generate(self, prompt: str, schema=None):
        if schema is not None:
            return self._llm.with_structured_output(schema).invoke(prompt)
        return self._llm.invoke(prompt).content  # type: ignore[return-value]

    async def a_generate(self, prompt: str, schema=None):
        if schema is not None:
            return await self._llm.with_structured_output(schema).ainvoke(prompt)
        result = await self._llm.ainvoke(prompt)
        return result.content  # type: ignore[return-value]

    def get_model_name(self) -> str:
        return f"Gemini ({self._model_name})"


insurance_contexts = [
    [
        "<context>This chunk is part of the section \"C. Types Of Term Insurance\" which details different variations of Term Insurance policies, specifically focusing on Decreasing Term Insurance and its application in Mortgage Insurance.</context>\n# C2. Decreasing Term Insurance\n\n2.9 As the name implies, a Decreasing Term Insurance policy provides a diminishing amount of cover over the term of the policy. The death benefit begins at a certain amount and then gradually decreases over the term of coverage according to the stated method that is described in the policy. For example, the benefit of a 5-year Decreasing Term Insurance policy may be $\\$ \\$ 50,000$ for the first year of coverage, decreasing by $\\$ 10,000$ on each policy anniversary2 , until it reaches $\\$ \\$ 0$ at the expiry of the fifth year.\n\n2.10 Insurers do offer different types of Decreasing Term Insurance, such as Mortgage Insurance, Credit Life Insurance, and Family Income Insurance, etc. Let us explore Mortgage Decreasing Term Insurance further.\n\n2.11 In a Mortgage Decreasing Term Insurance, at any point in time, the death benefit is designed to be equal to the remaining balance on the loan. As the balance on the loan gets smaller, the death benefit will also get smaller.\n\n2.12 However, it is important to note that the sum assured on each policy anniversary under a Mortgage Decreasing Term Insurance is based on what the remaining balance on the loan would be assuming a particular mortgage interest rate (insurers will usually offer a choice) and assuming that loan repayments are made on schedule. The sum assured on each policy anniversary is fixed, using these assumptions, when the policy is taken out.\n\n2.13 This means that, if anything causes the actual remaining loan balance to be different from what was initially expected, the sum assured will not be equal to the remaining loan balance. This happens quite often: for example, when mortgage interest rates change or loan repayment instalment amounts are changed. Therefore, when the death benefit is paid out, it may not equal the remaining loan balance; it may be more or it may be less.\n\n2.14 Mortgage Decreasing Term Insurance can also be issued on a joint-life, first-todie basis. This policy is suitable for a husband and wife who are jointly servicing their housing loan. As the sum assured under this policy is paid only once,",
        "<context>This chunk discusses Mortgage Decreasing Term Insurance, its features, suitability for joint loans, premium structure, and provides a visual representation of a decreasing term policy. It is part of the section explaining different types of Term Insurance.</context>\nit may be more or it may be less.\n\n2.14 Mortgage Decreasing Term Insurance can also be issued on a joint-life, first-todie basis. This policy is suitable for a husband and wife who are jointly servicing their housing loan. As the sum assured under this policy is paid only once, it means that you should advise those clients who are buying Joint-Mortgage Decreasing Term Insurance policies to insure the full amount of their outstanding housing loan (to cover the unfortunate case where both die, for example, in a car accident).\n\n2.15 The premium for a Decreasing Term Insurance policy is usually level and ceases a few years before the expiry of the policy. This is because the coverage towards the end of the policy term will be reduced considerably, and the policy owner may find that it is not worth paying the premium for the low coverage. Thus, most insurers structure the premium payment period this way to prevent the policy owner from terminating the policy. Figure 4.3 is a graphical representation of a 10-year $\\$ 100,000$ Decreasing Term Insurance policy where the sum assured decreases by a fixed amount each year.\n\n  \nFigure 4.3: A 10-Year $\\$ 100,000$ Decreasing Term Insurance Policy",
        "<context>This chunk is about the \"Decreasing Term Rider,\" which is a type of \"Term Rider.\" The document discusses various riders that can be attached to a basic life insurance policy to provide supplementary benefits. The \"Term Rider\" section (D) explains different types of term riders, including Level Term Rider, Family Income Benefit Rider, and Decreasing Term Rider. This specific chunk elaborates on the features, purpose, and application of the Decreasing Term Rider.</context>\n# D3. Decreasing Term Rider\n\n1.137 A decreasing Term Rider is the same as the level Term Rider, except that the sum assured for this rider decreases yearly.\n\n1.138 It is normally issued in periods of 10, 15 and 20 years, etc. As the sum assured decreases yearly, the amount of cover in the last few years of the rider term is usually very small.\n\n1.139 As the premium is level throughout the term of the policy, the policy owner may feel that it is not worthwhile to pay the premium for such a small amount of coverage and may decide to drop this rider.\n\n1.140 To avoid such a situation, most insurers will arrange for the policy owner to pay the premium for less than the full duration of the rider, yet the coverage will still continue to the full term of the rider. For example, some insurers do not require the policy owner to pay the premiums in the last four years prior to the expiry of this rider.\n\n1.141 Like the Decreasing Term Insurance, a decreasing Term Rider can be used by a policy owner to protect the mortgage on his home. In fact, this is the most common reason for anyone to attach this rider to his policy, as the premium is cheaper than the stand-alone Decreasing Term Insurance policy.",
        "<context>This chunk defines and explains various types of Term Insurance, including Level Term, Decreasing Term, Mortgage Decreasing Term, Increasing Term, and optional features like Renewable Options.</context>\n# Chapter summary:\n\n- Definition or Explanation: Term Insurance\nThis type of insurance provides life insurance cover for a specific period of time,called the policy term. People usually buy Term Insurance when they needtemporary insurance protection,i.e. the buyers are not looking for insurance fortheir entire life. Once the policy expires, the cover will cease and the insured willreceive nothing. The sum assured (or death benefit) of the policy is payable to thebeneficiaries only if the life insured dies during the policy term. That is why TermInsurance is also known as temporary insurance.\n\n- Definition or Explanation: Level Term Insurance\nThe simplest and most straightforward type of life insurance policy. It is called a Level Term policy because both the death benefit and the premium remain level throughout the policy term. Level term is designed to meet a constant need.\n\n- Definition or Explanation: Decreasing Term\nThis type of policy provides a diminishing amount of cover over the term of thepolicy. The death benefit begins at a certain amount and then gradually decreasesover the term of coverage according to the stated method that is described in thepolicy.\n\n- Definition or Explanation: Mortgage Decreasing TermInsurance\nFor this policy, at any point in time, the death benefit is designed to be equal to the remaining balance on the loan. As the balance on the loan gets smaller, the deathbenefit will also get smaller.\n\n- Definition or Explanation: Increasing Term Insurance\nThis type of policy is not common in Singapore. Its purpose is to protect the deathbenefit against the effect of inflation. An Increasing Term Insurance policy providesa death benefit that starts from one amount and increases by some specifiedamount or percentage at stated intervals over the policy term.\n\n- Definition or Explanation: Renewable Options\nThis option gives the life insured the right to renew his policy at the end of the policy term, without evidence of insurability. Most insurers offer this type of policy on a short-term basis. Renewal is allowed, as long as the expiry date of the policydoes not exceed a specified age (usually the age of 60 years).\n\n- Definition or Explanation:",
         "<context>This chunk discusses Joint Life Policies, a sub-classification of life insurance policies based on ownership, detailing \"First-to-die\" and \"Last Survivor\" types.</context>\n# B. Joint Life Policy\n\n5.3 Generally, this policy provides cover for two lives (usually limited to only husband and wife). Note that, although the vast majority of joint life policies have two lives insured, it is theoretically possible to have more if insurable interest exists. It can be issued in either of the following ways:\n\nFirst-to-die Life Insurance; or Last Survivor Life Insurance.\n\n5.4 The First-to-die Life Insurance policy pays on the death of one of the lives insured. The death benefit is paid to the surviving life insured and the policy cover ends. An example of this type of policy is a Joint Mortgage Decreasing Term Insurance policy, usually taken at the request of the bank, as a collateral security for the housing loan which the bank has granted.\n\n5.5 The Last Survivor Life Insurance (also known as Second-to-die Life Insurance) policy, on the other hand, only pays out the death benefit when both the lives insured have died i.e. on the second death. The premiums for this type of policy may be payable only until the first life insured dies or until the death of both lives insured. However, this type of policy is not common in Singapore.",
      ]
                      ]


evolution_config = EvolutionConfig(
    evolutions={
        Evolution.REASONING: 1/4,
        Evolution.MULTICONTEXT: 1/4,
        Evolution.CONCRETIZING: 1/4,
        Evolution.CONSTRAINED: 1/4,
    },
    num_evolutions=4
)

gemini_llm = GeminiDeepEvalLLM(MODEL_NAME)
synthesizer = Synthesizer(styling_config=styling_config, model=gemini_llm, evolution_config=evolution_config)
goldens = synthesizer.generate_goldens_from_contexts(
    contexts=insurance_contexts,
    # max_goldens_per_context=2,  # Generates up to 2 multi-turn scenarios per text block
)

output_path = Path(__file__).resolve().parent / "generated_goldens.json"
serialized_goldens = [
    golden.model_dump() if hasattr(golden, "model_dump") else dict(golden.__dict__)
    for golden in goldens
]

existing = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else []
output_path.write_text(
    json.dumps(existing + serialized_goldens, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
