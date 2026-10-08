from pathlib import Path

from app.contracts import BenchmarkDataset, BenchmarkItem


def _resolve_data_root() -> Path:
    """从任意运行目录都能定位到仓库根的 data 目录。"""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "data"
        if (candidate / "samples").is_dir():
            return candidate
    return Path.cwd() / "data"


DATA_ROOT = _resolve_data_root()
SAMPLES_ROOT = DATA_ROOT / "samples"


def load_experiment_fixture(schema_name: str) -> BenchmarkDataset:
    dataset_key = dataset_key_for(schema_name)
    item_ids = DATASET_ITEM_IDS[dataset_key]
    items: list[BenchmarkItem] = []
    for item_id in item_ids:
        html_path = SAMPLES_ROOT / f"{item_id}.html"
        if not html_path.exists():
            raise FileNotFoundError(f"benchmark sample file not found: {html_path}")
        items.append(
            BenchmarkItem(
                item_id=item_id,
                url=f"file://{html_path}",
                html=html_path.read_text(encoding="utf-8"),
                schema_name=schema_name,
                schema_spec=fixture_schema_for(schema_name),
                gold_record=gold_record_for(item_id),
            )
        )
    return BenchmarkDataset(
        name="中文网页实验 fixture（显式 Schema）",
        items=items,
    )


def dataset_key_for(schema_name: str) -> str:
    if schema_name == "招聘公告":
        return "job_posting"
    if schema_name == "政务公开 / 政策法规":
        return "government_policy"
    return "university_notice"


def fixture_schema_for(schema_name: str):
    """Return an explicit experiment-only schema; never used by runtime defaults."""
    from app.contracts import FieldSpec, SchemaSpec

    fields_by_domain = {
        "高校通知": [
            ("title", "标题", "text", True),
            ("publish_date", "发布日期", "date", False),
            ("department", "发布部门", "text", False),
            ("deadline", "报名截止日期", "date", False),
            ("contact", "联系人及联系方式", "text", False),
        ],
        "招聘公告": [
            ("title", "公告标题", "text", True),
            ("organization", "招聘单位", "text", False),
            ("position", "岗位名称", "text", False),
            ("publish_date", "发布日期", "date", False),
            ("deadline", "报名截止日期", "date", False),
        ],
        "政务公开 / 政策法规": [
            ("title", "文件标题", "text", True),
            ("document_number", "文号", "text", False),
            ("issuing_authority", "发布机关", "text", False),
            ("publish_date", "发布日期", "date", False),
            ("effective_date", "生效日期", "date", False),
        ],
    }
    return SchemaSpec(
        name=f"{schema_name}（实验样本）",
        domain="experiment_fixture",
        description="仅供 benchmark fixture 显式传入，不是系统默认 Schema。",
        fields=[
            FieldSpec(name=name, description=description, type=field_type, required=required)
            for name, description, field_type, required in fields_by_domain.get(
                schema_name, fields_by_domain["高校通知"]
            )
        ],
    )


# Backward-compatible test fixture import. Production code must pass a dataset explicitly.
load_builtin_dataset = load_experiment_fixture


DATASET_ITEM_IDS: dict[str, list[str]] = {
    "university_notice": [
        "university_notice_001",
        "university_notice_002",
        "university_notice_003",
    ],
    "job_posting": [
        "job_posting_001",
        "job_posting_002",
        "job_posting_003",
    ],
    "government_policy": [
        "government_policy_001",
        "government_policy_002",
        "government_policy_003",
    ],
}


def gold_record_for(item_id: str) -> dict[str, str]:
    if item_id == "job_posting_002":
        return {
            "title": "计算机学院2026年科研助理招聘公告",
            "organization": "计算机学院",
            "position": "科研助理",
            "publish_date": "2026-06-08",
            "deadline": "2026-07-05",
        }
    if item_id == "job_posting_003":
        return {
            "title": "图书馆2026年信息服务员招聘公告",
            "organization": "图书馆",
            "position": "信息服务员",
            "publish_date": "2026-05-28",
            "deadline": "2026-06-18",
        }
    if item_id == "government_policy_002":
        return {
            "title": "关于进一步规范科研经费使用的通知",
            "document_number": "科财〔2026〕8号",
            "issuing_authority": "财政局",
            "publish_date": "2026-04-15",
            "effective_date": "2026-05-01",
        }
    if item_id == "government_policy_003":
        return {
            "title": "关于推进政务服务标准化建设的通知",
            "document_number": "政服〔2026〕15号",
            "issuing_authority": "政务服务局",
            "publish_date": "2026-03-20",
            "effective_date": "2026-04-01",
        }
    if item_id == "university_notice_002":
        return {
            "title": "关于组织2026年暑期社会实践的通知",
            "publish_date": "2026-06-18",
            "department": "学生工作处",
            "deadline": "2026-07-10",
            "contact": "李老师，联系电话：010-87654321",
        }
    if item_id == "university_notice_003":
        return {
            "title": "关于开展2026年研究生奖学金评审工作的通知",
            "publish_date": "2026-05-22",
            "department": "研究生院",
            "deadline": "2026-06-20",
            "contact": "王老师，联系电话：010-99887766",
        }
    if item_id == "job_posting_001":
        return {
            "title": "信息工程学院2026年实验员招聘公告",
            "organization": "信息工程学院",
            "position": "实验员",
            "publish_date": "2026-06-01",
            "deadline": "2026-06-30",
        }
    return {
        "title": "关于开展2026年大学生创新训练项目申报的通知",
        "publish_date": "2026-06-12",
        "department": "教务处",
        "deadline": "2026-06-30",
        "contact": "张老师，联系电话：010-12345678",
    }
