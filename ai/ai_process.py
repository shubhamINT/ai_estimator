
import pprint
import asyncio
from collections import defaultdict
from ai.ai_instructions import (FEATURE_LISTING_INSTRUCTION, 
                                BRAINSTORM_SYSTEM_INSTRUCTION, 
                                REVIEW_SYSTEM_INSTRUCTION, 
                                FINAL_SYSTEM_INSTRUCTION,
                                METADATA_SYSTEM_INSTRUCTION,
                                PROJECT_TYPE_INSTRUCTION)
# Feature list structure
from structure import EstimationResponse, RankingResponse, Metadatastructure, ProjectType, FeatureList_Structure
from ai.ai_models import gemini_call, openai_call
import json
import yaml

class Ai_process:
    
    def __init__(self):
        self.openai_model_list = ["gpt-4.1", "gpt-5-mini", "gpt-5"]
        self.gemini_model_list = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-3-pro-preview"]
        # self.openai_model_list = ["gpt-4.1-mini"]
        # self.gemini_model_list = ["gemini-flash-latest"]
        self.gemini_final_model = "gemini-3-pro-preview"
        self.openai_final_model = "gpt-5.1"
        self.openai_metadata_model = "gpt-4.1"
        self.openai_featurelist_model = "gpt-5"

    async def combine_results(self):
        # Load ranked (rank) file
        with open("combined_ranked_json.json", encoding="utf-8") as f:
            ranked = json.load(f)

        # Load model result file
        with open("combined_json.json", encoding="utf-8") as f2:
            models = json.load(f2)

        # Calculate average ranks and collect reasons per Result
        rank_sums = defaultdict(int)
        rank_counts = defaultdict(int)
        reasons = defaultdict(list)

        for entry in ranked:
            for r in entry["ranks"]:
                result = r["Result"]
                rank = r["rank"]
                reason = r["reason"]
                rank_sums[result] += rank
                rank_counts[result] += 1
                reasons[result].append(reason)

        average_ranks = {result: rank_sums[result]/rank_counts[result] for result in rank_sums}

        # Map average rank and reasons to each model entry by Result
        for m in models:
            result = m["Result"]
            avg_rank = average_ranks.get(result)
            model_reasons = reasons.get(result, [])
            m["average_rank"] = avg_rank
            m["reasons"] = model_reasons

        # Save the updated models
        with open("combined_json_final.json", "w", encoding="utf-8") as f:
            json.dump(models, f, indent=4)

    # Feature listing
    async def feature_list(self, user_query:str, file_list = None):
        try:
            print("Understnading the features...")

            res = await openai_call(system_prompt = FEATURE_LISTING_INSTRUCTION, 
                                user_prompt = user_query,
                                file_list = file_list,
                                output_structure = FeatureList_Structure, 
                                model=self.openai_featurelist_model)
            print("Got the features...")

            return {"status": 0,"message": "Feature list generated", "data": res}
        except Exception as e:
            return{"status": -1, "message": str(e)}

    # Project type for DB operation
    async def predict_project_type(self, user_query:str, file_list = None):
        try:
            print("Understnading the type of project...")

            res = await openai_call(system_prompt = PROJECT_TYPE_INSTRUCTION, 
                                user_prompt = user_query,
                                file_list = file_list,
                                output_structure = ProjectType, 
                                model=self.openai_metadata_model)
            print("Got the type of project...")

            return {"response": res}
        except Exception as e:
            return{"status": -1, "message": str(e)}

    # Brainstorm
    async def brainstorm_stage(self, user_query:str, 
                               file_list = None, 
                               previos_estimations = None, 
                               openai_model_list = None, 
                               gemini_model_list = None,
                               feature_list = None):
        
        print("Processing the brainstorm stage...")

        brainstorm_instruction = BRAINSTORM_SYSTEM_INSTRUCTION

        # Format previous estimations for prompt (if present)
        if previos_estimations:
            # If it's a dict, list, or table, pretty-print as Markdown
            prev_text = (
                f"\nThese are some similar project estimations for your guidance:\n\n"
                f"```\n{previos_estimations if isinstance(previos_estimations, str) else pprint.pformat(previos_estimations)}\n```"
            )
            brainstorm_instruction += prev_text
            
        # Format feature list for prompt (if present)
        if feature_list:
            # If it's a list, join as human-readable Markdown list
            if isinstance(feature_list, (list, tuple)):
                feature_text = "\n".join(f"- {f}" for f in feature_list)
            else:
                feature_text = str(feature_list)
            brainstorm_instruction += (
                f"\n\n ## Following are the features of the project." 
                f"Calculate the estimation for each of these features:-\n\n{feature_text}\n"
            )

        # Create tasks for all OpenAI models
        openai_tasks = [
            openai_call(brainstorm_instruction, user_query,file_list, EstimationResponse, model=model)
            for model in openai_model_list
        ]

        # Create tasks for all Gemini models
        gemini_tasks = [
            gemini_call(brainstorm_instruction, user_query,file_list, EstimationResponse, model=model)
            for model in gemini_model_list
        ]

        # Run all tasks in parallel
        results = await asyncio.gather(*(openai_tasks + gemini_tasks), return_exceptions=True)

        # Split the results based on list sizes
        openai_results = results[:len(openai_tasks)]
        gemini_results = results[len(openai_tasks):]

        # Filter out exceptions
        def is_not_exception(res):
            return not isinstance(res, Exception)

        # Create a lableing in json with the response and model name
        openai_results = [{"model": model, "response": result} for model, result in zip(openai_model_list, openai_results) if is_not_exception(result)]
        gemini_results = [{"model": model, "response": result} for model, result in zip(gemini_model_list, gemini_results) if is_not_exception(result)]

        # combine the results
        combined_json = openai_results + gemini_results

        # Add "serial": "a", "b", ... to each item
        for i, entry in enumerate(combined_json):
            entry["Result"] = f"{chr(ord('A') + i)}"

        # Save the combined JSON to a file
        with open("combined_json.json", "w") as f:
            json.dump(combined_json, f, indent=2)

        print("Finished the brainstorm stage...")
    
    # Ranking
    async def ranking_stage(self, file_list = None, 
                            previos_estimations = None,
                            openai_model_list = None, 
                            gemini_model_list = None):
        print("Processing the ranking stage...")

        # Read the combined JSON file
        with open("combined_json.json", "r") as f:
            combined_json = json.load(f)

        # Prepare review results as a list of dicts for YAML
        review_list = []
        for entry in combined_json:
            review_list.append({"Result": entry['Result'], "Response": entry['response']})

        # Convert to YAML
        review_results_yaml = yaml.safe_dump(review_list, sort_keys=False, allow_unicode=True)

        # Build YAML review prompt
        review_user_prompt = (
            "### Responses to Review:-\n"
            f"{review_results_yaml}"
        )

        # If previos estimation add it with the system instruction
        if previos_estimations:
            review_system_prompt = (
                f"{REVIEW_SYSTEM_INSTRUCTION}\n\n"
                "These are some Similar project estimations take some guidance on review:-\n"
                f"{previos_estimations}\n"
            )
        else:
            review_system_prompt = REVIEW_SYSTEM_INSTRUCTION

        # Create tasks for all OpenAI models
        openai_tasks = [
            openai_call(review_system_prompt, review_user_prompt, file_list, RankingResponse, model=model)
            for model in openai_model_list
        ]

        # Create tasks for all Gemini models
        gemini_tasks = [
            gemini_call(review_system_prompt, review_user_prompt, file_list, RankingResponse, model=model)
            for model in gemini_model_list
        ]

        # Run all tasks in parallel
        results = await asyncio.gather(*(openai_tasks + gemini_tasks), return_exceptions=True)

        # Filter out exceptions
        def is_not_exception(res):
            return not isinstance(res, Exception)

        openai_results = [result for result in results[:len(openai_tasks)] if is_not_exception(result)]
        gemini_results = [result for result in results[len(openai_tasks):] if is_not_exception(result)]

        combined_ranked_json = openai_results + gemini_results

        # Save the combined JSON to a file
        with open("combined_ranked_json.json", "w") as f:
            json.dump(combined_ranked_json, f, indent=2)

        # Buld the final combined json
        await self.combine_results()

        print("Finished the ranking stage...")
    
    # Final
    async def final_stage(self, user_query:str , 
                          file_list = None, 
                          previos_estimations = None):
        print("Processing the final stage...")

        # Read the combined final JSON file
        with open("combined_json_final.json", "r") as f:
            combined_json_final = json.load(f)

        # Remove "model" from each entry
        entries_no_model = []
        for entry in combined_json_final:
            entry_copy = dict(entry)
            entry_copy.pop("model", None)
            entries_no_model.append(entry_copy)

         # Convert to YAML
        yaml_str = yaml.safe_dump(entries_no_model, sort_keys=False, allow_unicode=True)

        
        # If previos estimation add it with the system instruction
        if previos_estimations:
            final_prompt = (
                f"{FINAL_SYSTEM_INSTRUCTION}\n\n"
                "These are some Similar project estimations take some guidance:-\n"
                f"{previos_estimations}\n"
                "Following are the estimated results:-\n"
                f"{yaml_str}"
            )
        else:
            final_prompt = (
                f"{FINAL_SYSTEM_INSTRUCTION}\n\n"
                "Following are the estimated results:-\n"
                f"{yaml_str}"
            )
            
        res = await openai_call(final_prompt, user_query,file_list, EstimationResponse, model=self.openai_final_model)
        print("Finished the final stage...")

        return {"response": res}

    # Extract Metadata for db insert
    async def extract_metadata(self, markdown_text):
        print("Processing the metadata extraction stage...")

        res = await openai_call(system_prompt = METADATA_SYSTEM_INSTRUCTION, 
                                user_prompt = markdown_text, 
                                output_structure = Metadatastructure, 
                                model=self.openai_metadata_model)
        print("Finished the metadata extraction stage...")

        return {"response": res}