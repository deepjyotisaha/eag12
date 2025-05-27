import uuid
from utils.utils import log_step, log_error
from action.executor import run_user_code
from agent.agentSession import ExecutionSnapshot
from concurrent.futures import ThreadPoolExecutor
import asyncio
from config.log_config import setup_logging, logger_code_block

log = setup_logging(__name__)

executor = ThreadPoolExecutor(max_workers=3)  # Limit to 3 variants

async def execute_step(step_id, code, ctx, session, multi_mcp, variant_used: str = ""):
    result = None
    try:
        logger_code_block(log, f"Starting execution of step {step_id} (variant: {variant_used})", code)

        log.info(f"🔍 Executing code for step {step_id}")
        result = await run_user_code(code, multi_mcp, ctx.session_id)

        if session:
            snapshot = ExecutionSnapshot(
                run_id=str(uuid.uuid4()),
                step_id=step_id,
                variant_used=variant_used,
                code=code,
                status=result.get("status", "error"),
                    result=result.get("result"),
                    error=result.get("error"),
                    execution_time=result.get("execution_time", ""),
                    total_time=result.get("total_time", ""),
            )
            session.add_execution_snapshot(snapshot)
            logger_code_block(log, f"Execution snapshot for step {step_id}", None, snapshot.__dict__)
    except Exception as e:
        logger_code_block(log, f"Exception in step {step_id}", code, str(e))
        log.error(f"❌ Exception in step {step_id}: {str(e)}")
        result = {"status": "error", "error": str(e)}

    if result.get("status") == "success":
        ctx.update_step_result(step_id, result["result"])
        ctx.mark_step_completed(step_id)
        logger_code_block(log, f"Step {step_id} completed successfully", code, result)
    else:
        ctx.mark_step_failed(step_id, result.get("error", "Unknown error"))
        logger_code_block(log, f"Step {step_id} failed", code, result)
    return result


def run_step_in_thread(step_id, code, ctx, session, multi_mcp, variant):
    log.info(f"🔍 Running step {step_id} in thread (variant: {variant})")
    return asyncio.run(execute_step(step_id, code, ctx, session, multi_mcp, variant_used=variant))

async def execute_step_with_mode(step_id, code_variants, ctx, mode, session, multi_mcp):
    """Execute step with specified mode (parallel or fallback)"""
    log.info(f"🔍 Executing step {step_id} with mode {mode}")
    
    if mode == "parallel":
        log.info(f"🔄 Executing {len(code_variants)} tasks in parallel")
        loop = asyncio.get_event_loop()
        tasks = []
        variant_map = []

        # Log available variants
        log.info(f"📋 Available code variants for step {step_id}:")
        logger_code_block(log, f"Available code variants for step {step_id}", None, code_variants)
        for suffix in ["A", "B", "C"]:
            variant = f"CODE_{step_id}{suffix}"
            if variant in code_variants:
                code = code_variants[variant]
                #log.info(f"📝 Variant {variant}:\n{code}")
                variant_map.append(variant)
                tasks.append(
                    loop.run_in_executor(
                        executor,
                        run_step_in_thread,
                        step_id, code, ctx, session, multi_mcp, variant
                    )
                )

        if not tasks:
            log.error(f"❌ No valid variants found for step {step_id}")
            return {"status": "error", "error": "No valid variants to run."}

        log.info(f"🔄 Executing {len(tasks)} tasks in parallel")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_results = []
        for variant, result in zip(variant_map, results):
            if isinstance(result, Exception):
                log.error(f"❌ Variant {variant} failed with exception: {str(result)}")
                all_results.append({"status": "error", "error": str(result), "variant": variant})
                logger_code_block(log, f"Variant {variant} failed with exception: {str(result)}", None, result)
            else:
                result["variant"] = variant
                log.info(f"📊 Variant {variant} result: {result}")
                all_results.append(result)
                logger_code_block(log, f"Variant {variant} result: {result}", None, result)

        for result in all_results:
            if result.get("status") == "success":
                log.info(f"✅ Success with variant {result['variant']}: {result['result']}")
                logger_code_block(log, f"Success with variant {result['variant']}: {result['result']}", None, result)
                return {"status": "success", "results": all_results, "result": result["result"]}

        log.error(f"❌ All variants failed for step {step_id}")
        logger_code_block(log, f"All variants failed for step {step_id}", None, all_results)
        return {"status": "error", "results": all_results, "error": "All variants failed."}

    else:  # fallback mode
        log.info(f"🔄 Executing {len(code_variants)} tasks in fallback mode")
        
        result = None
        for suffix in ["A", "B", "C"]:
            variant = f"CODE_{step_id}{suffix}"
            if variant not in code_variants:
                log.info(f"⏭️ Skipping variant {variant} - not available")
                continue
                
            code = code_variants[variant]
            try:
                # Log attempt to execute variant
                #logger_code_block(log, f"Attempting variant {variant}", code)
                log.info(f"🔍 Attempting variant {variant}")
                
                result = await execute_step(step_id, code, ctx, session, multi_mcp, variant_used=variant)
                
                if result.get("status") == "success":
                    logger_code_block(log, f"✅ Variant {variant} succeeded", code, result)
                    log_step(f"✅ Variant {variant} succeeded.", symbol="✅")
                    log.info(f"✅ Variant {variant} succeeded - returning result without processing other variants as its fallback mode")
                    return result
                else:
                    logger_code_block(log, f"❌ Variant {variant} failed", code, {
                        "error": result.get("error"),
                        "status": result.get("status"),
                        "result": result.get("result")
                    })
                    log_error(f"❌ Variant {variant} failed: {result.get('error')}")
            except Exception as e:
                logger_code_block(log, f"💥 Exception in variant {variant}", code, {
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                })
                log_error(f"❌ Exception in variant {variant}: {e}")

        
        log.error(f"❌ All variants failed during fallback execution for step {step_id}")
        log_error(f"❌ All variants failed during fallback execution for step {step_id}")
        if result and result.get("status") == "error":
            log.error(f"↳ Error: {result.get('error')}")
            log_error(f"↳ Error: {result.get('error')}")

        return {"status": "error", "error": "All fallback variants failed."}
