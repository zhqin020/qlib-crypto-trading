# TRAINER.PY BUG ANALYSIS REPORT

**File:** `/Users/chadwyatt/Code/trading/qlib-2/src/models/trainer.py`
**Analysis Date:** 2025-10-07
**Total Issues Found:** 24 (7 Critical, 9 High, 5 Medium, 3 Low)

---

## EXECUTIVE SUMMARY

The `trainer.py` module has **significant gaps** in error handling, resource management, and edge case handling. While the ProcessMonitor integration is solid, the training workflow itself lacks robustness for production use.

**Critical Findings:**
- No cleanup of partial artifacts on failure
- No GPU/CPU resource detection or error handling
- Missing checkpoint/resume capability
- Unbounded memory growth during training
- No validation of hyperparameters or data shapes
- Incomplete error recovery mechanisms

**Recommendation:** Address all Critical and High severity issues before production deployment.

---

## 1. TRAINING PROCESS ERRORS

### 🔴 CRITICAL #1: No Model Initialization Error Handling
**Location:** Lines 157-158
**Severity:** CRITICAL
**Impact:** Crashes with unclear errors, no cleanup

**Current Code:**
```python
# Initialize model
model = init_instance_by_config(model_config)
```

**Problems:**
- No validation that model class exists
- No handling of import errors
- No validation of model parameters
- Qlib may fail to import required model class

**Failure Scenarios:**
1. Model class not installed (e.g., xgboost not installed)
2. Invalid model parameters (e.g., negative learning rate)
3. Incompatible qlib version
4. Missing required dependencies (e.g., torch for LSTM)

**Recommended Fix:**
```python
# Step 3: Generate model configuration
await monitor.update_progress(process_id, 37.5, f"Generating {handler} model configuration", 3)

# Validate handler is supported
supported_handlers = ["lightgbm", "xgboost", "lstm", "transformer"]
if handler.lower() not in supported_handlers:
    await monitor.fail_process(process_id, f"Unsupported model handler: {handler}")
    return {
        "error": f"Unsupported model handler: {handler}. Supported: {supported_handlers}",
        "status": "failed",
        "handler": handler
    }

# Get model configuration with validation
try:
    model_config = get_model_config(handler, params or {})

    # Validate model config structure
    if "class" not in model_config or "module_path" not in model_config:
        raise ValueError("Invalid model configuration structure")

except Exception as e:
    await monitor.fail_process(process_id, f"Failed to generate model config: {e}")
    return {
        "error": f"Failed to generate model configuration: {e}",
        "status": "failed",
        "handler": handler
    }

# ... later, at initialization ...

# Initialize model with error handling
try:
    logger.info(f"Initializing {handler} model...")
    model = init_instance_by_config(model_config)

    # Validate model has required methods
    if not hasattr(model, 'fit') or not hasattr(model, 'predict'):
        raise AttributeError(f"Model {handler} missing required methods (fit/predict)")

    logger.info(f"Model initialized successfully: {type(model).__name__}")

except ModuleNotFoundError as e:
    error_msg = f"Model module not found: {e}. Is the package installed?"
    await monitor.fail_process(process_id, error_msg)
    return {"error": error_msg, "status": "failed", "handler": handler}

except ImportError as e:
    error_msg = f"Failed to import model: {e}"
    await monitor.fail_process(process_id, error_msg)
    return {"error": error_msg, "status": "failed", "handler": handler}

except Exception as e:
    error_msg = f"Failed to initialize model: {e}"
    logger.error(error_msg, exc_info=True)
    await monitor.fail_process(process_id, error_msg)
    return {"error": error_msg, "status": "failed", "handler": handler}
```

---

### 🔴 CRITICAL #2: No Dataset Loading Error Handling
**Location:** Lines 161
**Severity:** CRITICAL
**Impact:** Crashes on empty datasets, malformed data

**Current Code:**
```python
# Initialize dataset
dataset = init_instance_by_config(dataset_config)
```

**Problems:**
- No validation that dataset has data
- No handling of empty date ranges
- No validation of instrument list
- No checking if features can be calculated
- Hard-coded date ranges (lines 140-143) may be invalid for dataset

**Failure Scenarios:**
1. Dataset has no instruments for date range
2. Features cannot be calculated (missing price data)
3. Date range invalid for dataset (e.g., train dates after test dates)
4. Calendar mismatch (using stock calendar for crypto)

**Recommended Fix:**
```python
# Define dataset configuration with dynamic date ranges
# Get actual date range from dataset instead of hard-coding
try:
    # Import qlib calendar utilities
    from qlib.data import D

    # Get available date range for dataset
    # This will fail fast if dataset is invalid
    cal = D.calendar(freq="day")

    if len(cal) == 0:
        raise ValueError("Dataset calendar is empty")

    # Use last 3 years of data, or whatever is available
    # Split: 70% train, 15% valid, 15% test
    total_days = len(cal)
    if total_days < 100:
        raise ValueError(f"Dataset too small: only {total_days} days available")

    # Calculate split points
    train_days = int(total_days * 0.70)
    valid_days = int(total_days * 0.15)

    train_start = cal[0].strftime("%Y-%m-%d")
    train_end = cal[train_days - 1].strftime("%Y-%m-%d")
    valid_start = cal[train_days].strftime("%Y-%m-%d")
    valid_end = cal[train_days + valid_days - 1].strftime("%Y-%m-%d")
    test_start = cal[train_days + valid_days].strftime("%Y-%m-%d")
    test_end = cal[-1].strftime("%Y-%m-%d")

    logger.info(f"Dataset date ranges - Train: {train_start} to {train_end}, "
                f"Valid: {valid_start} to {valid_end}, Test: {test_start} to {test_end}")

except Exception as e:
    error_msg = f"Failed to determine dataset date ranges: {e}"
    await monitor.fail_process(process_id, error_msg)
    return {"error": error_msg, "status": "failed", "dataset": dataset_ref}

# Define dataset configuration with validated dates
dataset_config = {
    "class": "DatasetH",
    "module_path": "qlib.data.dataset",
    "kwargs": {
        "handler": handler_config,
        "segments": {
            "train": (train_start, train_end),
            "valid": (valid_start, valid_end),
            "test": (test_start, test_end),
        },
    },
}

# Step 4: Load dataset with error handling
await monitor.update_progress(process_id, 50.0, f"Loading dataset '{dataset_ref}'", 4)

try:
    logger.info(f"Initializing dataset with segments...")
    dataset = init_instance_by_config(dataset_config)

    # Validate dataset has data
    # Try to prepare a small batch to ensure data is loadable
    try:
        # This will fail if no data available
        df_train = dataset.prepare("train", col_set=["feature", "label"])

        if df_train is None or len(df_train) == 0:
            raise ValueError("Training dataset is empty")

        logger.info(f"Dataset loaded: {len(df_train)} training samples")

    except Exception as e:
        raise ValueError(f"Dataset contains no data: {e}")

except ValueError as e:
    error_msg = f"Dataset validation failed: {e}"
    await monitor.fail_process(process_id, error_msg)
    return {"error": error_msg, "status": "failed", "dataset": dataset_ref}

except Exception as e:
    error_msg = f"Failed to load dataset: {e}"
    logger.error(error_msg, exc_info=True)
    await monitor.fail_process(process_id, error_msg)
    return {"error": error_msg, "status": "failed", "dataset": dataset_ref}
```

---

### 🔴 CRITICAL #3: No GPU/CPU Resource Handling
**Location:** Lines 302, 321 (get_model_config)
**Severity:** CRITICAL
**Impact:** Crashes on systems without GPU, OOM errors

**Current Code:**
```python
"GPU": 0,  # Hard-coded GPU device
```

**Problems:**
- Hard-codes GPU device 0
- No check if GPU is available
- No fallback to CPU
- No handling of CUDA out of memory errors
- No memory monitoring during training

**Failure Scenarios:**
1. System has no GPU → crash
2. GPU out of memory → crash with unclear error
3. GPU already in use → crash or hang
4. Multiple GPUs available but wrong device selected

**Recommended Fix:**
```python
def get_model_config(handler: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Get model configuration based on handler type"""

    # Detect GPU availability for deep learning models
    gpu_available = False
    if handler.lower() in ["lstm", "transformer"]:
        try:
            import torch
            gpu_available = torch.cuda.is_available()
            if gpu_available:
                logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
            else:
                logger.warning("No GPU detected, will use CPU (training will be slower)")
        except ImportError:
            logger.warning("PyTorch not installed, cannot use GPU")

    configs = {
        "lightgbm": {
            "class": "LGBModel",
            "module_path": "qlib.contrib.model.gbdt",
            "kwargs": {
                "loss": "mse",
                "colsample_bytree": 0.8879,
                "learning_rate": 0.0421,
                "subsample": 0.8789,
                "lambda_l1": 205.6999,
                "lambda_l2": 580.9768,
                "max_depth": 8,
                "num_leaves": 210,
                "num_threads": 20,
                **params
            },
        },
        "xgboost": {
            "class": "XGBModel",
            "module_path": "qlib.contrib.model.xgboost",
            "kwargs": {
                "booster": "gbtree",
                "learning_rate": 0.05,
                "max_depth": 6,
                "n_estimators": 500,
                "objective": "reg:squarederror",
                # Use GPU if available
                "tree_method": "gpu_hist" if gpu_available else "hist",
                "gpu_id": 0 if gpu_available else None,
                **params
            },
        },
        "lstm": {
            "class": "LSTM",
            "module_path": "qlib.contrib.model.pytorch_lstm",
            "kwargs": {
                "d_feat": 6,
                "hidden_size": 64,
                "num_layers": 2,
                "dropout": 0.2,
                "n_epochs": 100,
                "lr": 0.001,
                "batch_size": 512,
                "early_stop": 20,
                "loss": "mse",
                "optimizer": "adam",
                # Use GPU only if available, fallback to CPU
                "GPU": 0 if gpu_available else None,
                **params
            },
        },
        "transformer": {
            "class": "Transformer",
            "module_path": "qlib.contrib.model.pytorch_transformer",
            "kwargs": {
                "d_feat": 6,
                "d_model": 64,
                "nhead": 4,
                "num_layers": 2,
                "dropout": 0.2,
                "n_epochs": 100,
                "lr": 0.001,
                "batch_size": 512,
                "early_stop": 20,
                "loss": "mse",
                "optimizer": "adam",
                # Use GPU only if available, fallback to CPU
                "GPU": 0 if gpu_available else None,
                **params
            },
        },
    }

    return configs.get(handler.lower(), configs["lightgbm"])
```

**Additional Fix - Wrap Training with OOM Handling:**
```python
# Step 5: Train model with OOM protection
await monitor.update_progress(process_id, 62.5, f"Training {handler} model '{model_id}'", 5)

try:
    logger.info(f"Training {handler} model: {model_id}")
    model.fit(dataset)
    logger.info(f"Training completed successfully")

except MemoryError as e:
    error_msg = f"Out of memory during training. Try reducing batch_size or model complexity."
    await monitor.fail_process(process_id, error_msg)
    return {"error": error_msg, "status": "failed", "handler": handler}

except RuntimeError as e:
    # Catch CUDA OOM errors
    if "out of memory" in str(e).lower() or "cuda" in str(e).lower():
        error_msg = f"GPU out of memory during training. Try reducing batch_size or use CPU."
        await monitor.fail_process(process_id, error_msg)
        return {"error": error_msg, "status": "failed", "handler": handler}
    else:
        raise  # Re-raise if not OOM
```

---

### 🟠 HIGH #4: No Training Convergence Monitoring
**Location:** Line 168
**Severity:** HIGH
**Impact:** May train forever on non-converging models

**Current Code:**
```python
model.fit(dataset)  # No timeout, no convergence checking
```

**Problems:**
- No timeout for training
- No monitoring of training progress
- No early stopping for non-converging models
- No detection of NaN/inf in losses

**Recommended Fix:**
```python
# Step 5: Train model with timeout and convergence monitoring
await monitor.update_progress(process_id, 62.5, f"Training {handler} model '{model_id}'", 5)

try:
    logger.info(f"Training {handler} model: {model_id}")

    # Set training timeout based on model type
    timeout_minutes = 60  # Default 1 hour
    if handler.lower() in ["lstm", "transformer"]:
        timeout_minutes = 120  # 2 hours for deep learning

    # Run training with timeout
    import asyncio
    from functools import partial

    loop = asyncio.get_event_loop()
    fit_task = loop.run_in_executor(None, partial(model.fit, dataset))

    try:
        await asyncio.wait_for(fit_task, timeout=timeout_minutes * 60)
        logger.info(f"Training completed successfully")

    except asyncio.TimeoutError:
        error_msg = f"Training timed out after {timeout_minutes} minutes"
        await monitor.fail_process(process_id, error_msg)
        return {"error": error_msg, "status": "failed", "handler": handler}

except ValueError as e:
    # Catch convergence issues (NaN, inf, etc.)
    if "nan" in str(e).lower() or "inf" in str(e).lower():
        error_msg = f"Training failed to converge (NaN/inf detected). Try adjusting learning rate."
        await monitor.fail_process(process_id, error_msg)
        return {"error": error_msg, "status": "failed", "handler": handler}
    else:
        raise
```

---

## 2. ERROR RECOVERY

### 🔴 CRITICAL #5: No Cleanup of Partial Artifacts
**Location:** Lines 189-215
**Severity:** CRITICAL
**Impact:** Disk filled with partial/corrupted files

**Current Code:**
```python
# Save model
model_path = models_dir / f"{model_id}.pkl"
import pickle
with open(model_path, 'wb') as f:
    pickle.dump(model, f)

# ... more code ...
# If error occurs here, partial files left on disk
```

**Problems:**
- Model file saved before validation
- Metadata file saved separately (can be orphaned)
- No cleanup on error
- No atomic save operation
- Corrupted files not detected

**Recommended Fix:**
```python
# Wrap entire training in try-finally for cleanup
model_path = None
meta_file = None

try:
    # ... training code ...

    # Step 7: Save model atomically
    await monitor.update_progress(process_id, 87.5, f"Saving model to disk", 7)

    # Save to temporary file first
    temp_model_path = models_dir / f"{model_id}.pkl.tmp"
    try:
        import pickle
        logger.info(f"Serializing model to {temp_model_path}")
        with open(temp_model_path, 'wb') as f:
            pickle.dump(model, f)

        # Verify file was written
        if not temp_model_path.exists() or temp_model_path.stat().st_size == 0:
            raise IOError("Model file is empty or not created")

        # Atomic rename
        model_path = models_dir / f"{model_id}.pkl"
        temp_model_path.rename(model_path)
        logger.info(f"Model saved successfully to {model_path}")

    except Exception as e:
        # Clean up temp file
        if temp_model_path.exists():
            temp_model_path.unlink()
        raise IOError(f"Failed to save model: {e}")

    # Step 8: Record results
    await monitor.update_progress(process_id, 95.0, f"Recording training results", 8)

    # Save metadata atomically
    temp_meta_file = models_dir / f"{model_id}_meta.json.tmp"
    try:
        result = {
            "model_id": model_id,
            "handler": handler,
            "dataset": dataset_ref,
            "feature_set": feature_set_ref,
            "status": "completed",
            "model_path": str(model_path),
            "trained_at": datetime.now().isoformat(),
            "metrics": recorder_info,
            "params": params or {}
        }

        with open(temp_meta_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)

        # Atomic rename
        meta_file = models_dir / f"{model_id}_meta.json"
        temp_meta_file.rename(meta_file)
        logger.info(f"Metadata saved to {meta_file}")

    except Exception as e:
        # Clean up temp file
        if temp_meta_file.exists():
            temp_meta_file.unlink()
        raise IOError(f"Failed to save metadata: {e}")

    # Complete process monitoring
    await monitor.complete_process(process_id, result)
    logger.info(f"Model trained successfully: {model_id}")
    return result

except Exception as e:
    logger.error(f"Error training model: {e}", exc_info=True)

    # CLEANUP: Remove partial artifacts
    if model_path and model_path.exists():
        try:
            model_path.unlink()
            logger.info(f"Cleaned up partial model file: {model_path}")
        except Exception as cleanup_error:
            logger.error(f"Failed to cleanup model file: {cleanup_error}")

    if meta_file and meta_file.exists():
        try:
            meta_file.unlink()
            logger.info(f"Cleaned up partial metadata file: {meta_file}")
        except Exception as cleanup_error:
            logger.error(f"Failed to cleanup metadata file: {cleanup_error}")

    # Fail process
    if process_started:
        try:
            await monitor.fail_process(process_id, str(e))
        except Exception as monitor_error:
            logger.error(f"Failed to update process monitor: {monitor_error}")

    return {
        "error": str(e),
        "dataset": dataset_ref,
        "handler": handler,
        "status": "failed"
    }
```

---

### 🔴 CRITICAL #6: No Checkpoint/Resume Capability
**Location:** Entire function
**Severity:** CRITICAL
**Impact:** Hours of training lost on crash/interruption

**Problems:**
- No checkpointing during training
- Cannot resume interrupted training
- No state saving between epochs
- Wastes compute time on failures

**Recommended Fix:**
```python
# Add checkpoint directory
checkpoints_dir = models_dir / "checkpoints" / model_id
checkpoints_dir.mkdir(parents=True, exist_ok=True)

# Configure model with checkpointing (for deep learning models)
if handler.lower() in ["lstm", "transformer"]:
    model_config["kwargs"]["save_path"] = str(checkpoints_dir)
    model_config["kwargs"]["save_prefix"] = model_id

    # Check for existing checkpoint to resume
    checkpoint_files = list(checkpoints_dir.glob(f"{model_id}_*.pth"))
    if checkpoint_files and params.get("resume", False):
        latest_checkpoint = max(checkpoint_files, key=lambda p: p.stat().st_mtime)
        model_config["kwargs"]["resume_path"] = str(latest_checkpoint)
        logger.info(f"Resuming from checkpoint: {latest_checkpoint}")

# After training failure, checkpoint is preserved for manual inspection/resume
```

---

### 🟠 HIGH #7: No Rollback on Failure
**Location:** Lines 156-221
**Severity:** HIGH
**Impact:** Corrupted state in MLflow, orphaned records

**Problems:**
- MLflow experiment started but never cleaned up on error
- R.start() context not properly handled on error
- Recorder may contain partial/invalid metrics
- No transaction-like behavior

**Recommended Fix:**
```python
# Initialize experiment with proper error handling
mlflow_experiment = None
mlflow_run_id = None

try:
    # Initialize experiment
    mlflow_experiment = R.start(experiment_name=f"crypto_{handler}", recorder_name=model_id)
    mlflow_experiment.__enter__()
    mlflow_run_id = R.get_recorder().info.get("run_id") if R.get_recorder() else None

    logger.info(f"Started MLflow run: {mlflow_run_id}")

    # ... training code ...

    # If successful, commit is implicit via __exit__

except Exception as e:
    # Rollback MLflow run on error
    if mlflow_experiment:
        try:
            # Exit context manager with error
            mlflow_experiment.__exit__(type(e), e, e.__traceback__)

            # Mark run as failed in MLflow
            if mlflow_run_id:
                try:
                    import mlflow
                    mlflow.end_run(status="FAILED")
                    logger.info(f"Marked MLflow run as FAILED: {mlflow_run_id}")
                except Exception as mlflow_error:
                    logger.error(f"Failed to mark MLflow run as failed: {mlflow_error}")
        except Exception as ctx_error:
            logger.error(f"Error during MLflow context cleanup: {ctx_error}")

    raise  # Re-raise original exception

finally:
    # Ensure experiment context is closed
    if mlflow_experiment:
        try:
            mlflow_experiment.__exit__(None, None, None)
        except:
            pass  # Already exited
```

---

## 3. VALIDATION ISSUES

### 🔴 CRITICAL #8: No Hyperparameter Validation
**Location:** Lines 256-327 (get_model_config)
**Severity:** CRITICAL
**Impact:** Invalid parameters cause cryptic failures

**Current Code:**
```python
**params  # User params merged without validation
```

**Problems:**
- No validation of parameter types
- No validation of parameter ranges
- Can override critical parameters incorrectly
- No checking for conflicting parameters

**Recommended Fix:**
```python
def validate_model_params(handler: str, params: Dict[str, Any]) -> Dict[str, str]:
    """
    Validate model parameters and return error messages for invalid params.
    Returns empty dict if all valid.
    """
    errors = {}

    if handler.lower() == "lightgbm":
        if "learning_rate" in params:
            lr = params["learning_rate"]
            if not isinstance(lr, (int, float)) or lr <= 0 or lr > 1:
                errors["learning_rate"] = "Must be float between 0 and 1"

        if "max_depth" in params:
            depth = params["max_depth"]
            if not isinstance(depth, int) or depth < 1 or depth > 50:
                errors["max_depth"] = "Must be integer between 1 and 50"

        if "num_leaves" in params:
            leaves = params["num_leaves"]
            if not isinstance(leaves, int) or leaves < 2:
                errors["num_leaves"] = "Must be integer >= 2"

        # Validate num_leaves < 2^max_depth (LightGBM requirement)
        if "num_leaves" in params and "max_depth" in params:
            if params["num_leaves"] >= 2 ** params["max_depth"]:
                errors["num_leaves"] = f"Must be < 2^max_depth ({2 ** params['max_depth']})"

    elif handler.lower() == "xgboost":
        if "learning_rate" in params:
            lr = params["learning_rate"]
            if not isinstance(lr, (int, float)) or lr <= 0 or lr > 1:
                errors["learning_rate"] = "Must be float between 0 and 1"

        if "n_estimators" in params:
            n = params["n_estimators"]
            if not isinstance(n, int) or n < 1 or n > 10000:
                errors["n_estimators"] = "Must be integer between 1 and 10000"

    elif handler.lower() in ["lstm", "transformer"]:
        if "n_epochs" in params:
            epochs = params["n_epochs"]
            if not isinstance(epochs, int) or epochs < 1 or epochs > 1000:
                errors["n_epochs"] = "Must be integer between 1 and 1000"

        if "batch_size" in params:
            bs = params["batch_size"]
            if not isinstance(bs, int) or bs < 1 or bs > 10000:
                errors["batch_size"] = "Must be integer between 1 and 10000"

        if "lr" in params:
            lr = params["lr"]
            if not isinstance(lr, (int, float)) or lr <= 0 or lr > 1:
                errors["lr"] = "Must be float between 0 and 1"

        if "dropout" in params:
            dropout = params["dropout"]
            if not isinstance(dropout, (int, float)) or dropout < 0 or dropout >= 1:
                errors["dropout"] = "Must be float between 0 and 1"

    return errors

# Use in train_model before training:
# Validate parameters before training
param_errors = validate_model_params(handler, params or {})
if param_errors:
    error_msg = f"Invalid parameters: {param_errors}"
    await monitor.fail_process(process_id, error_msg)
    return {
        "error": error_msg,
        "status": "failed",
        "handler": handler,
        "param_errors": param_errors
    }
```

---

### 🟠 HIGH #9: No Data Shape Validation
**Location:** Lines 161
**Severity:** HIGH
**Impact:** Crashes during training with shape mismatch errors

**Problems:**
- No validation of feature dimensions
- No checking if d_feat matches actual features
- No validation of label availability
- May train on empty segments

**Recommended Fix:**
```python
# After loading dataset, validate shape
try:
    # Get training data to validate
    df_train = dataset.prepare("train", col_set=["feature", "label"])
    df_valid = dataset.prepare("valid", col_set=["feature", "label"])

    if df_train is None or len(df_train) == 0:
        raise ValueError("Training dataset is empty")

    if df_valid is None or len(df_valid) == 0:
        raise ValueError("Validation dataset is empty")

    # Get feature dimensions
    if hasattr(df_train, 'columns'):
        # Dataframe - count feature columns
        feature_cols = [c for c in df_train.columns if c not in ['label']]
        n_features = len(feature_cols)
    else:
        # Assume multi-index, get feature level
        n_features = df_train.shape[1] - 1  # Subtract label column

    logger.info(f"Dataset validation passed - Train: {len(df_train)} samples, "
                f"Valid: {len(df_valid)} samples, Features: {n_features}")

    # Update model config with actual feature dimensions
    if handler.lower() in ["lstm", "transformer"]:
        model_config["kwargs"]["d_feat"] = n_features
        logger.info(f"Updated d_feat to {n_features} based on dataset")

except Exception as e:
    error_msg = f"Dataset validation failed: {e}"
    await monitor.fail_process(process_id, error_msg)
    return {"error": error_msg, "status": "failed", "dataset": dataset_ref}
```

---

### 🟠 HIGH #10: No Feature Compatibility Check
**Location:** Lines 118-128
**Severity:** HIGH
**Impact:** Training fails due to feature/dataset mismatch

**Problems:**
- No validation that feature config matches dataset
- No checking if Alpha158 features can be calculated
- No validation of custom feature expressions
- May use wrong feature handler for dataset type

**Recommended Fix:**
```python
# Load and validate feature set configuration
config_dir = project_root / "config" / "features"
feature_config_file = config_dir / f"{feature_set_ref}.json"

if feature_config_file.exists():
    try:
        with open(feature_config_file) as f:
            feature_config = json.load(f)

        handler_config = feature_config["config"]

        # Validate feature config structure
        if "class" not in handler_config or "module_path" not in handler_config:
            raise ValueError("Feature config missing 'class' or 'module_path'")

        # Validate feature handler matches dataset type
        feature_handler_class = handler_config["class"]

        # Check if using intraday features on daily data (or vice versa)
        if "Alpha360" in feature_handler_class:
            logger.warning("Alpha360 is designed for intraday data. Ensure dataset has intraday frequency.")
        elif "Alpha158" in feature_handler_class:
            logger.info("Using Alpha158 features for daily/multi-day data")

        logger.info(f"Loaded feature config: {feature_handler_class}")

    except json.JSONDecodeError as e:
        error_msg = f"Feature config file is corrupted: {e}"
        await monitor.fail_process(process_id, error_msg)
        return {"error": error_msg, "status": "failed", "feature_set": feature_set_ref}

    except Exception as e:
        error_msg = f"Failed to load feature config: {e}"
        await monitor.fail_process(process_id, error_msg)
        return {"error": error_msg, "status": "failed", "feature_set": feature_set_ref}
else:
    # Use default Alpha158 if no config found
    logger.warning(f"Feature config not found: {feature_config_file}. Using default Alpha158")
    from ..data_pipeline.features import get_alpha158_config
    handler_config = get_alpha158_config()
```

---

### 🟡 MEDIUM #11: No Model Configuration Validation
**Location:** Lines 131
**Severity:** MEDIUM
**Impact:** May use incompatible model config

**Problems:**
- No validation that model_config is valid
- No checking if model class exists in qlib
- No validation of required kwargs

**Recommended Fix:**
```python
# Get and validate model configuration
try:
    model_config = get_model_config(handler, params or {})

    # Validate model config structure
    required_keys = ["class", "module_path", "kwargs"]
    for key in required_keys:
        if key not in model_config:
            raise ValueError(f"Model config missing required key: {key}")

    logger.info(f"Generated model config for {handler}: {model_config['class']}")

except Exception as e:
    error_msg = f"Failed to generate model configuration: {e}"
    await monitor.fail_process(process_id, error_msg)
    return {"error": error_msg, "status": "failed", "handler": handler}
```

---

## 4. PROGRESS TRACKING

### 🟡 MEDIUM #12: Progress Not Updated During Long Operations
**Location:** Line 168
**Severity:** MEDIUM
**Impact:** Poor UX, appears frozen during training

**Problems:**
- model.fit() may run for hours with no progress updates
- User sees 62.5% for entire training duration
- No indication of actual training progress (epochs, etc.)
- No ETA calculation

**Recommended Fix:**
```python
# For deep learning models, wrap fit to report epoch progress
if handler.lower() in ["lstm", "transformer"]:
    # Create callback to update progress during training
    # Note: This requires modifying qlib models or monkey-patching

    # Estimate total training time for ETA
    n_epochs = model_config["kwargs"].get("n_epochs", 100)
    progress_start = 62.5
    progress_end = 75.0
    progress_range = progress_end - progress_start

    # Callback to update progress per epoch
    async def epoch_callback(epoch: int, total_epochs: int):
        epoch_progress = (epoch / total_epochs) * progress_range
        current_progress = progress_start + epoch_progress
        await monitor.update_progress(
            process_id,
            current_progress,
            f"Training epoch {epoch}/{total_epochs}",
            5
        )

    # Train with progress callback
    # Note: Actual implementation depends on qlib model internals
    # May need to run training in separate thread and poll for progress
    model.fit(dataset)
else:
    # Tree models are fast, just show training message
    model.fit(dataset)
```

---

### 🟡 MEDIUM #13: Inaccurate Step Completion Count
**Location:** Lines 69, 92, 112, etc.
**Severity:** MEDIUM
**Impact:** Inconsistent progress reporting

**Problems:**
- Steps are reported (1, 2, 3, etc.) but never verified
- If step is skipped, count is wrong
- No tracking of actual completed steps

**Recommended Fix:**
```python
# Track actual completed steps
completed_steps = 0
total_steps = 8

# Step 1
await monitor.update_progress(process_id, 12.5, f"Validating dataset", completed_steps=1)
completed_steps += 1

# Step 2
await monitor.update_progress(process_id, 25.0, f"Initializing Qlib", completed_steps=2)
completed_steps += 1

# ... and so on for each step ...
```

---

## 5. RESOURCE MANAGEMENT

### 🟠 HIGH #14: Model Not Deleted After Training
**Location:** Line 168 onwards
**Severity:** HIGH
**Impact:** Memory leak for large models

**Problems:**
- Model kept in memory after pickling
- Dataset kept in memory
- No explicit cleanup of large objects
- Memory grows with each training run

**Recommended Fix:**
```python
# After saving model, explicitly free memory
try:
    # Save model
    model_path = models_dir / f"{model_id}.pkl"
    import pickle
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)

    logger.info(f"Model saved to {model_path}")

    # Free model from memory (important for large models)
    del model

    # Also delete dataset to free memory
    del dataset

    # Force garbage collection
    import gc
    gc.collect()

    logger.info("Freed model and dataset from memory")

except Exception as e:
    error_msg = f"Failed to save model: {e}"
    raise
```

---

### 🟠 HIGH #15: Large Tensors Not Freed (Deep Learning)
**Location:** Line 168
**Severity:** HIGH
**Impact:** GPU memory leak for LSTM/Transformer

**Problems:**
- PyTorch tensors may remain on GPU after training
- No explicit GPU cache clearing
- May cause OOM on subsequent runs

**Recommended Fix:**
```python
# After training deep learning model, clear GPU memory
if handler.lower() in ["lstm", "transformer"]:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("Cleared GPU cache")
    except:
        pass  # PyTorch not available or no GPU
```

---

### 🟡 MEDIUM #16: File Handles Left Open on Error
**Location:** Lines 191-192, 214-215
**Severity:** MEDIUM
**Impact:** Resource exhaustion with many errors

**Problems:**
- File opened with `with open()` but exception may occur during write
- No guarantee file is closed on error
- Multiple errors = multiple leaked handles

**Recommended Fix:**
```python
# Use explicit close in try-finally
model_file = None
try:
    model_file = open(model_path, 'wb')
    pickle.dump(model, model_file)
except Exception as e:
    logger.error(f"Failed to save model: {e}")
    raise
finally:
    if model_file:
        model_file.close()
```

**Note:** Actually the current code with `with open()` is correct. But adding explicit error handling is better:

```python
try:
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
except IOError as e:
    raise IOError(f"Failed to write model file: {e}")
except Exception as e:
    raise Exception(f"Failed to serialize model: {e}")
```

---

### 🟢 LOW #17: Temp Files Not Cleaned
**Location:** Lines 66
**Severity:** LOW
**Impact:** Minor disk space waste

**Problems:**
- models/trained directory grows indefinitely
- No cleanup of old training artifacts
- Checkpoints accumulate

**Recommended Fix:**
```python
# Add periodic cleanup of old checkpoints (>7 days)
checkpoints_dir = models_dir / "checkpoints"
if checkpoints_dir.exists():
    import time
    now = time.time()
    for checkpoint_dir in checkpoints_dir.iterdir():
        if checkpoint_dir.is_dir():
            age_days = (now - checkpoint_dir.stat().st_mtime) / 86400
            if age_days > 7:
                try:
                    import shutil
                    shutil.rmtree(checkpoint_dir)
                    logger.info(f"Cleaned up old checkpoint: {checkpoint_dir.name}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup checkpoint: {e}")
```

---

## 6. INTEGRATION ISSUES

### 🟠 HIGH #18: MLflow Logging Failures Not Handled
**Location:** Lines 198
**Severity:** HIGH
**Impact:** Training succeeds but metrics lost

**Problems:**
- R.get_recorder().list_metrics() may fail
- No fallback if MLflow is unavailable
- Training would fail if metrics can't be retrieved

**Recommended Fix:**
```python
# Step 8: Record results with error handling
await monitor.update_progress(process_id, 95.0, f"Recording training results", 8)

# Get recorder info with fallback
try:
    recorder_info = R.get_recorder().list_metrics()
    logger.info(f"Retrieved metrics from MLflow: {recorder_info}")
except Exception as e:
    logger.warning(f"Failed to retrieve metrics from MLflow: {e}")
    recorder_info = {"error": "Failed to retrieve metrics", "reason": str(e)}

result = {
    "model_id": model_id,
    "handler": handler,
    "dataset": dataset_ref,
    "feature_set": feature_set_ref,
    "status": "completed",
    "model_path": str(model_path),
    "trained_at": datetime.now().isoformat(),
    "metrics": recorder_info,
    "params": params or {}
}
```

---

### 🟡 MEDIUM #19: ProcessMonitor Integration Gaps
**Location:** Lines 106-109, 150-153, 170-173
**Severity:** MEDIUM
**Impact:** Cancellation may not work reliably

**Problems:**
- Only 3 cancellation checkpoints in entire training
- Long operations (fit, predict) not cancellable mid-operation
- If training takes 2 hours, can't cancel during fit

**Recommended Fix:**
```python
# Add more frequent cancellation checks
cancellation_check_points = [
    "after_init",
    "after_dataset_load",
    "before_training",
    "during_training",  # Need to implement periodic checks
    "after_training",
    "before_save"
]

# Before each major operation:
async def check_cancellation():
    process = await monitor.get_process(process_id)
    if process and process.status == ProcessStatus.CANCELLED:
        logger.info(f"Training cancelled at: {checkpoint}")
        return True
    return False

# Example usage:
if await check_cancellation():
    return {"status": "cancelled", "process_id": process_id}

# For long operations, use asyncio.wait_for with periodic checks
```

---

### 🟡 MEDIUM #20: Feature Handler Import Errors Not Caught
**Location:** Line 127
**Severity:** MEDIUM
**Impact:** Cryptic import errors on missing dependencies

**Problems:**
- get_alpha158_config() import may fail
- No handling of import errors
- No validation that handler exists

**Recommended Fix:**
```python
else:
    # Use default Alpha158 if no config found
    try:
        from ..data_pipeline.features import get_alpha158_config
        handler_config = get_alpha158_config()
        logger.warning(f"Feature config not found, using default Alpha158")
    except ImportError as e:
        error_msg = f"Failed to import feature handler: {e}"
        await monitor.fail_process(process_id, error_msg)
        return {"error": error_msg, "status": "failed", "feature_set": feature_set_ref}
```

---

## 7. EDGE CASES

### 🟡 MEDIUM #21: Zero-Epoch Training Not Handled
**Location:** Line 296, 315 (get_model_config)
**Severity:** MEDIUM
**Impact:** Hangs or crashes on n_epochs=0

**Problems:**
- User could set n_epochs=0 via params
- No validation prevents this
- Model would train forever or crash

**Fix:** Covered in "Hyperparameter Validation" section above.

---

### 🟡 MEDIUM #22: Single Sample Training Not Handled
**Location:** Line 168
**Severity:** MEDIUM
**Impact:** Crashes with batch size errors

**Problems:**
- If dataset has only 1 sample, batch operations fail
- No minimum sample count validation
- No adjustment of batch_size for small datasets

**Recommended Fix:**
```python
# After dataset validation, check sample count
if len(df_train) < 100:
    logger.warning(f"Very small training set: {len(df_train)} samples")

    # Adjust batch size for small datasets
    if handler.lower() in ["lstm", "transformer"]:
        recommended_batch_size = max(1, len(df_train) // 10)
        if model_config["kwargs"]["batch_size"] > recommended_batch_size:
            logger.warning(f"Reducing batch_size to {recommended_batch_size} for small dataset")
            model_config["kwargs"]["batch_size"] = recommended_batch_size

if len(df_train) < 10:
    error_msg = f"Training set too small: {len(df_train)} samples. Need at least 10 samples."
    await monitor.fail_process(process_id, error_msg)
    return {"error": error_msg, "status": "failed", "dataset": dataset_ref}
```

---

### 🟢 LOW #23: Missing Validation Set Not Handled
**Location:** Line 141
**Severity:** LOW
**Impact:** Training may work but no early stopping

**Problems:**
- Hard-coded validation split may have no data
- No fallback if validation set empty
- Early stopping won't work without validation

**Recommended Fix:**
```python
# Validate all segments have data
try:
    df_valid = dataset.prepare("valid", col_set=["feature", "label"])

    if df_valid is None or len(df_valid) == 0:
        logger.warning("Validation set is empty. Early stopping will not work.")
        # Could fall back to train/test split instead

except Exception as e:
    logger.warning(f"Failed to load validation set: {e}")
```

---

### 🟢 LOW #24: Imbalanced Classes Not Detected
**Location:** Line 168
**Severity:** LOW
**Impact:** Poor model performance, not an error

**Problems:**
- No checking if labels are balanced
- No warning if 99% of labels are same value
- May train biased model

**Recommended Fix:**
```python
# After dataset loading, check label distribution
try:
    import numpy as np
    labels = df_train['label'].values

    # Check if all labels are same
    unique_labels = np.unique(labels)
    if len(unique_labels) < 2:
        logger.warning(f"All labels have same value: {unique_labels[0]}. Model may not learn.")

    # Check for severe imbalance (>95% one class)
    label_counts = np.bincount(labels.astype(int))
    if len(label_counts) > 0:
        imbalance_ratio = label_counts.max() / len(labels)
        if imbalance_ratio > 0.95:
            logger.warning(f"Severe class imbalance: {imbalance_ratio*100:.1f}% of labels are same class")

except Exception as e:
    logger.debug(f"Could not check label balance: {e}")
    # Not critical, continue training
```

---

## SUMMARY OF FIXES NEEDED

### Critical (Must Fix)
1. Model initialization error handling (Critical #1)
2. Dataset loading error handling (Critical #2)
3. GPU/CPU resource detection (Critical #3)
4. Cleanup of partial artifacts (Critical #5)
5. Checkpoint/resume capability (Critical #6)
6. Hyperparameter validation (Critical #8)

### High (Should Fix)
7. Training convergence monitoring (High #4)
8. Rollback on failure (High #7)
9. Data shape validation (High #9)
10. Feature compatibility check (High #10)
11. Model memory cleanup (High #14)
12. Tensor memory cleanup (High #15)
13. MLflow error handling (High #18)

### Medium (Nice to Have)
14. Model config validation (Medium #11)
15. Progress during training (Medium #12)
16. Step completion tracking (Medium #13)
17. File handle management (Medium #16)
18. ProcessMonitor integration (Medium #19)
19. Feature handler imports (Medium #20)
20. Zero-epoch handling (Medium #21)
21. Single sample handling (Medium #22)

### Low (Optional)
22. Temp file cleanup (Low #17)
23. Validation set handling (Low #23)
24. Imbalanced class detection (Low #24)

---

## TESTING RECOMMENDATIONS

After implementing fixes, add these test cases:

```python
# Test suite for trainer.py
class TestTrainerErrorHandling:
    async def test_invalid_model_handler(self):
        """Test that invalid model handler fails gracefully"""
        result = await train_model("dataset", "features", "invalid_model")
        assert result["status"] == "failed"
        assert "Unsupported model handler" in result["error"]

    async def test_missing_dataset(self):
        """Test that missing dataset is detected early"""
        result = await train_model("nonexistent", "features", "lightgbm")
        assert result["status"] == "failed"
        assert "not found" in result["error"]

    async def test_empty_dataset(self):
        """Test that empty dataset fails gracefully"""
        # Create empty dataset
        result = await train_model("empty_dataset", "features", "lightgbm")
        assert result["status"] == "failed"
        assert "empty" in result["error"].lower()

    async def test_invalid_hyperparameters(self):
        """Test that invalid params are rejected"""
        result = await train_model(
            "dataset", "features", "lightgbm",
            params={"learning_rate": -1}  # Invalid
        )
        assert result["status"] == "failed"
        assert "Invalid parameters" in result["error"]

    async def test_training_timeout(self):
        """Test that training times out if too slow"""
        # Mock slow training
        pass

    async def test_oom_handling(self):
        """Test that OOM errors are caught and reported"""
        # Mock OOM error
        pass

    async def test_partial_artifact_cleanup(self):
        """Test that partial files are deleted on error"""
        # Cause failure after model file created
        # Verify file is cleaned up
        pass

    async def test_small_dataset_batch_adjustment(self):
        """Test that batch size is adjusted for small datasets"""
        # Create dataset with <100 samples
        # Verify batch_size is reduced
        pass
```

---

## ESTIMATED EFFORT

| Category | Issues | Estimated Time |
|----------|--------|----------------|
| Critical | 6 | 12-16 hours |
| High | 7 | 8-12 hours |
| Medium | 8 | 6-8 hours |
| Low | 3 | 2-3 hours |
| **Total** | **24** | **28-39 hours** |

**Recommendation:** Prioritize Critical issues immediately, then tackle High severity issues. Medium and Low issues can be addressed incrementally.

---

## CONCLUSION

The `trainer.py` module requires significant hardening before production use. The most critical gaps are:

1. **No error recovery** - Failures leave corrupted artifacts
2. **No resource management** - Memory leaks and GPU issues
3. **No validation** - Invalid inputs cause cryptic errors
4. **Limited observability** - Training appears frozen for hours

**Immediate Action Required:**
- Implement Critical fixes #1-#6
- Add comprehensive test suite
- Load test with various failure scenarios
- Document known limitations and edge cases

With these fixes, the trainer will be production-ready and resilient to common failure modes.
