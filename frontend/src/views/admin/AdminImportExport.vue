<template>
  <section class="page">
    <div class="panel hero">
      <div>
        <h1>导入导出</h1>
        <p>下载任务导入模板，或导出当前任务报表。导入解析会在下一阶段补成完整流程。</p>
      </div>
    </div>

    <div class="panel">
      <div class="toolbar">
        <a class="button" href="/api/v1/tasks/import-template" target="_blank" rel="noreferrer">下载导入模板</a>
        <a class="button secondary" href="/api/v1/reports/export" target="_blank" rel="noreferrer">导出任务报表</a>
      </div>
      <div class="muted-block">
        当前导入接口已经预留，下一阶段会补上 Excel/CSV 上传、字段校验和失败行回显。
      </div>
    </div>
  </section>
</template>
