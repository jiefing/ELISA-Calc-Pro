# -*- coding: utf-8 -*-
"""
用户自定义模型管理对话框 (user_model_dialog.py) - V3.0
增删改用户模型表达式，实时校验并显示检测到的参数，
保存到 user_models.json，退出后由主窗口刷新模型列表。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QLineEdit, QPushButton,
    QLabel, QMessageBox, QSplitter, QFrame,
)
from PyQt5.QtCore import Qt

from core.expression_parser import validate_expression, ExpressionError, FUNCTION_LIB, SPECIAL_VARS
from math_engine import load_user_model_definitions, save_user_model_definitions


class UserModelDialog(QDialog):
    """用户自定义模型编辑器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义模型管理")
        self.resize(660, 420)
        self._defs = load_user_model_definitions()
        self._dirty = False

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：模型列表
        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("已保存模型："))
        self.list_models = QListWidget()
        self.list_models.currentRowChanged.connect(self._load_selected)
        left_layout.addWidget(self.list_models)
        btn_new = QPushButton("新建模型")
        btn_del = QPushButton("删除选中")
        btn_new.clicked.connect(self._new_model)
        btn_del.clicked.connect(self._delete_selected)
        left_layout.addWidget(btn_new)
        left_layout.addWidget(btn_del)
        splitter.addWidget(left)

        # 右侧：编辑器
        right = QFrame()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("模型名称："))
        self.edit_name = QLineEdit()
        right_layout.addWidget(self.edit_name)
        right_layout.addWidget(QLabel("模型表达式（自变量 x，参数为单个字母）："))
        self.edit_expr = QLineEdit()
        self.edit_expr.setPlaceholderText("例如：a + b*exp(-c*x)")
        right_layout.addWidget(self.edit_expr)
        self.lbl_params = QLabel("检测参数：—")
        self.lbl_params.setWordWrap(True)
        self.lbl_params.setStyleSheet("color: #0B5ED7;")
        right_layout.addWidget(self.lbl_params)
        self.lbl_check = QLabel("")
        self.lbl_check.setWordWrap(True)
        self.lbl_check.setStyleSheet("color: #198754;")
        right_layout.addWidget(self.lbl_check)
        hint = QLabel(
            "可用函数：" + " ".join(sorted(FUNCTION_LIB.keys())) + "\n"
            "特殊变量：" + ", ".join(SPECIAL_VARS) + "\n"
            "运算符：+ - * / ^ 与比较 < > <= >= == !=（结果为 0/1，可构造分段模型）"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; font-size: 8pt;")
        right_layout.addWidget(hint)
        right_layout.addStretch(1)
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("保存修改")
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_save)
        right_layout.addLayout(btn_row)
        splitter.addWidget(right)

        splitter.setSizes([220, 440])
        layout.addWidget(splitter, stretch=1)

        btn_close_row = QHBoxLayout()
        btn_close_row.addStretch(1)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_close_row.addWidget(btn_close)
        layout.addLayout(btn_close_row)

        self.btn_save.clicked.connect(self._save_current)
        self.edit_expr.textChanged.connect(self._validate_live)
        self._refresh_list()

    # ---------------- 列表管理 ----------------
    def _refresh_list(self, select_row: int = -1):
        self.list_models.blockSignals(True)
        self.list_models.clear()
        for d in self._defs:
            self.list_models.addItem(d["name"])
        self.list_models.blockSignals(False)
        if self._defs:
            row = select_row if 0 <= select_row < len(self._defs) else 0
            self.list_models.setCurrentRow(row)
            self._load_selected(row)
        else:
            self.edit_name.clear()
            self.edit_expr.clear()
            self.lbl_params.setText("检测参数：—")
            self.lbl_check.setText("")

    def _load_selected(self, row: int):
        if 0 <= row < len(self._defs):
            d = self._defs[row]
            self.edit_name.setText(d["name"])
            self.edit_expr.setText(d["expression"])
            self._validate_live()

    def _new_model(self):
        self._defs.append({"name": f"自定义模型 {len(self._defs) + 1}", "expression": "a + b*x"})
        self._refresh_list(select_row=len(self._defs) - 1)
        self.edit_expr.setFocus()

    def _delete_selected(self):
        row = self.list_models.currentRow()
        if row < 0:
            return
        name = self._defs[row]["name"]
        if QMessageBox.question(self, "确认删除", f"确定删除模型“{name}”吗？") != QMessageBox.Yes:
            return
        del self._defs[row]
        self._dirty = True
        self._save_defs()
        self._refresh_list()

    # ---------------- 编辑与校验 ----------------
    def _validate_live(self):
        expr = self.edit_expr.text().strip()
        if not expr:
            self.lbl_params.setText("检测参数：—")
            self.lbl_check.setText("")
            return
        try:
            params = validate_expression(expr)
            self.lbl_params.setText("检测参数：" + (", ".join(params) if params else "（无参数，仅使用数据统计量）"))
            self.lbl_check.setText("✔ 表达式语法正确")
            self.lbl_check.setStyleSheet("color: #198754;")
        except ExpressionError as e:
            self.lbl_params.setText("检测参数：—")
            self.lbl_check.setText(f"✘ {e}")
            self.lbl_check.setStyleSheet("color: #DC3545;")

    def _save_current(self):
        row = self.list_models.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择或新建一个模型。")
            return
        name = self.edit_name.text().strip()
        expr = self.edit_expr.text().strip()
        if not name:
            QMessageBox.warning(self, "名称无效", "模型名称不能为空。")
            return
        if not expr:
            QMessageBox.warning(self, "表达式无效", "表达式不能为空。")
            return
        try:
            validate_expression(expr)
        except ExpressionError as e:
            QMessageBox.warning(self, "表达式错误", str(e))
            return
        # 重名检查（除自身外）
        for i, d in enumerate(self._defs):
            if d["name"] == name and i != row:
                QMessageBox.warning(self, "名称重复", f"已存在名为“{name}”的模型。")
                return
        self._defs[row]["name"] = name
        self._defs[row]["expression"] = expr
        self._dirty = True
        self._save_defs()
        self._refresh_list(select_row=row)
        QMessageBox.information(self, "已保存", f"模型“{name}”已保存。")

    def _save_defs(self):
        try:
            save_user_model_definitions(self._defs)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"写入 user_models.json 失败：\n{e}")

    def accept(self):
        if self._dirty and callable(getattr(self.parent(), "_refresh_user_models", None)):
            self.parent()._refresh_user_models()
        super().accept()
