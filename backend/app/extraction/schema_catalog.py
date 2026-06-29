from app.domain import FieldSpec, SchemaSpec

DEFAULT_SCHEMA_NAME = "高校通知"


def get_builtin_schemas() -> dict[str, SchemaSpec]:
    return {
        "高校通知": SchemaSpec(
            name="高校通知",
            domain="university_notice",
            description="高校官网通知、公告、教务或科研通知抽取 schema。",
            fields=[
                FieldSpec(
                    name="title",
                    description="通知标题",
                    aliases=["标题", "通知标题"],
                    type="text",
                    required=True,
                ),
                FieldSpec(
                    name="publish_date",
                    description="发布日期",
                    aliases=["发布日期", "发布时间", "发布于", "日期"],
                    type="date",
                    required=True,
                ),
                FieldSpec(
                    name="department",
                    description="发布单位",
                    aliases=["发布单位", "来源", "部门", "学院"],
                    type="string",
                    required=False,
                ),
                FieldSpec(
                    name="deadline",
                    description="截止日期或报名截止时间",
                    aliases=["截止时间", "截止日期", "报名截止", "申报截止"],
                    type="date",
                    required=False,
                ),
                FieldSpec(
                    name="contact",
                    description="联系人或联系电话",
                    aliases=["联系人", "联系方式", "联系电话", "咨询电话"],
                    type="string",
                    required=False,
                ),
            ],
        ),
        "招聘公告": SchemaSpec(
            name="招聘公告",
            domain="job_posting",
            description="招聘公告、岗位发布和人才引进信息抽取 schema。",
            fields=[
                FieldSpec(
                    name="title",
                    description="公告标题",
                    aliases=["标题", "公告标题"],
                    type="text",
                    required=True,
                ),
                FieldSpec(
                    name="organization",
                    description="招聘单位",
                    aliases=["招聘单位", "单位", "公司", "部门"],
                    type="string",
                    required=True,
                ),
                FieldSpec(
                    name="position",
                    description="招聘岗位",
                    aliases=["岗位", "职位", "招聘岗位"],
                    type="string",
                    required=True,
                ),
                FieldSpec(
                    name="publish_date",
                    description="发布日期",
                    aliases=["发布日期", "发布时间", "日期"],
                    type="date",
                    required=False,
                ),
                FieldSpec(
                    name="deadline",
                    description="报名截止时间",
                    aliases=["报名截止", "截止时间", "截止日期"],
                    type="date",
                    required=False,
                ),
            ],
        ),
        "政务公开 / 政策法规": SchemaSpec(
            name="政务公开 / 政策法规",
            domain="government_policy",
            description="政务公开、政策法规、通知文件抽取 schema。",
            fields=[
                FieldSpec(
                    name="title",
                    description="文件标题",
                    aliases=["标题", "文件标题"],
                    type="text",
                    required=True,
                ),
                FieldSpec(
                    name="document_number",
                    description="文号",
                    aliases=["文号", "发文字号", "文件编号"],
                    type="string",
                    required=False,
                ),
                FieldSpec(
                    name="issuing_authority",
                    description="发布机关",
                    aliases=["发布机关", "发文机关", "发布单位"],
                    type="string",
                    required=True,
                ),
                FieldSpec(
                    name="publish_date",
                    description="发布日期",
                    aliases=["发布日期", "发布时间", "成文日期", "日期"],
                    type="date",
                    required=True,
                ),
                FieldSpec(
                    name="effective_date",
                    description="生效日期",
                    aliases=["生效日期", "施行日期", "执行日期"],
                    type="date",
                    required=False,
                ),
            ],
        ),
    }


def get_builtin_schema(name: str) -> SchemaSpec:
    schemas = get_builtin_schemas()
    if name in schemas:
        return schemas[name]
    return schemas[DEFAULT_SCHEMA_NAME]
