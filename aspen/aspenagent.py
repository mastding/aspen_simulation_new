import os
import json
import pandas as pd
import win32com.client
import pythoncom
from typing import Dict, List, Any, Optional
import time
from flask import Flask, request, jsonify
from datetime import datetime
from collections import deque
import traceback
from dotenv import load_dotenv
import openpyxl
import uuid
import tempfile

app = Flask(__name__)
# 全局变量存储控制面板消息
control_panel_messages = deque(maxlen=1000)  # 限制最多存储1000条消息

# 加载环境变量
load_dotenv('../.env', override=True)

class AspenSimulationManager:
    def __init__(self, aspen_executable_path: str = None):
        """
        初始化Aspen Plus模拟管理器

        Args:
            aspen_executable_path: Aspen Plus可执行文件路径(可选)
        """
        try:
            pythoncom.CoInitialize()
            self.aspen = win32com.client.Dispatch("Apwn.Document")
            print("成功连接到Aspen Plus")
            # 连接事件处理器
            self.aspen_events = win32com.client.WithEvents(self.aspen, AspenEvents)
        except Exception as e:
            print(f"无法连接到Aspen Plus: {e}")
            if aspen_executable_path and os.path.exists(aspen_executable_path):
                os.startfile(aspen_executable_path)
                # 等待Aspen启动
                time.sleep(5)
                self.aspen = win32com.client.Dispatch("Apwn.Document")
            else:
                raise Exception("无法启动Aspen Plus，请检查安装")

        # 添加获取控制面板消息的方法
    def get_control_panel_messages(self) -> str:
        """获取控制面板消息"""
        if hasattr(self, 'aspen_events'):
            return self.aspen_events.get_current_session_messages_as_string()
        return ""

    def create_new_simulation(self, template_path: str = None):
        """
        创建新的模拟文件

        Args:
            template_path: 模板文件路径(可选)
        """
        try:
            if template_path and os.path.exists(template_path):
                self.aspen.InitFromArchive2(template_path)
            else:
                self.aspen.InitFromArchive2("")  # 空模拟
            print("成功创建新模拟")

        except Exception as e:
            print(f"创建模拟失败: {e}")
            raise

    def load_json_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        加载JSON配置数据

        Args:
            config_data: JSON配置数据字典

        Returns:
            JSON配置字典
        """
        print("成功加载JSON配置数据")
        return config_data

    def get_child_nodes(self, parent_path: str) -> List[str]:
        """获取指定父节点下的所有子节点名称"""
        try:
            parent_node = self.aspen.Tree.FindNode(parent_path)
            if parent_node and parent_node.Elements.Count > 0:
                return [child.Name for child in parent_node.Elements]
            else:
                return []
        except Exception as e:
            print(f"获取 {parent_path} 子节点时出错: {e}")
            return []

    def safe_get_node_value(self, node_path: str) -> Any:
        """安全获取节点值"""
        try:
            node = self.aspen.Tree.FindNode(node_path)
            if node:
                return node.Value
            return None
        except Exception as e:
            print(f"获取节点 {node_path} 值时出错: {e}")
            return None

    def safe_get_node_units(self, node_path: str, default: Any = None) -> Any:
        """安全获取节点单位，避免节点不存在时抛出异常"""
        try:
            node = self.aspen.Tree.FindNode(node_path)
            if node:
                return node.UnitString
            else:
                return default
        except Exception as e:
            print(f"获取节点 {node_path} 单位时出错: {e}")
            return default

    def safe_set_node_value(self, node_path: str, value: Any) -> bool:
        """安全设置节点值"""
        try:
            node = self.aspen.Tree.FindNode(node_path)
            if node:
                node.Value = value
                return True
            return False
        except Exception as e:
            print(f"设置节点 {node_path} 值时出错: {e}")
            return False

    def convert_unitstr(self, s):
        conversion_map = {
            "bar": 5,
            "C": 4,
            "kmol/hr": 3,
            "kPa": 10, # 压力单位
            "kg/hr": 3, # 质量单位
            "kg": 3,
            "atm": 3,
            "kW": 14, # 负荷单位
            "Gcal/hr": 18,  # 负荷单位
            "kg/cum": 1, #颗粒密度单位
            "gm/cc": 3, #颗粒密度单位
            "gm/ml": 6, #颗粒密度单位
            "lb/bbl": 6, #颗粒密度单位
            "lb/cuft": 6, #颗粒密度单位
            "lb/gal": 4, #颗粒密度单位
            "cal/sec": 3, #负荷单位
            "MPa": 20,
            "": 0,
        }
        if s in conversion_map:
            return conversion_map[s]
        else:
            raise ValueError(f"无法转换字符串 '{s}'，未找到对应的转换规则")

    def write_config_to_aspen(self, config: Dict[str, Any]):
        """
        将所有配置写入Aspen模拟文件
        """
        print("开始将配置写入Aspen模拟文件...")
        self.write_setup_to_aspen(config)
        self.write_components_to_aspen(config)
        self.write_property_methods_to_aspen(config)
        self.write_blocks_to_aspen(config)
        self.write_stream_to_aspen(config)
        self.write_block_connections_to_aspen(config)
        self.write_stream_data_to_aspen(config)
        self.write_reactions_data_to_aspen(config)
        self.write_convergence_data_to_aspen(config)
        self.write_blocks_Mixer_data_to_aspen(config)
        self.write_blocks_Valve_data_to_aspen(config)
        self.write_blocks_Compr_data_to_aspen(config)
        self.write_blocks_Heater_data_to_aspen(config)
        self.write_blocks_Pump_data_to_aspen(config)
        self.write_blocks_RStoic_data_to_aspen(config)
        self.write_blocks_RPlug_data_to_aspen(config)
        self.write_blocks_Flash2_data_to_aspen(config)
        self.write_blocks_Decanter_data_to_aspen(config)
        self.write_blocks_Sep_data_to_aspen(config)
        self.write_blocks_Sep2_data_to_aspen(config)
        self.write_blocks_DSTWU_data_to_aspen(config)
        self.write_blocks_RadFrac_data_to_aspen(config)
        self.write_design_specs_data_to_aspen(config)
        print("所有数据提取完成")

    def write_setup_to_aspen(self, config: Dict[str, Any]):
        """
        将设置的配置写入Aspen模拟文件
        """
        try:
            sim_options = config.get("setup", {}).get("sim_options", {})
            ENERGY_BAL_NODE = self.aspen.Tree.FindNode(r"\Data\Setup\Sim-Options\Input\ENERGY_BAL")
            self.add_if_not_empty(sim_options, ENERGY_BAL_NODE, "energy_bal_value")
            print("成功添加setup")
        except Exception as e:
            print(f"在添加setup时出错: {e}")
            raise
    def write_components_to_aspen(self, config: Dict[str, Any]):
        """
        将配置写入Aspen模拟文件
        """
        try:
            # 添加组分
            try:
                aname1_node = self.aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\ANAME1")
                casn_node = self.aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CASN")
                for i, component in enumerate(config.get('components', [])):
                    if component.get('database_name') is not None:  # 只添加有数据库名称的组分
                        aname1_node.Elements.InsertRow(0, 0)
                        aname1_node.Elements.LabelNode(0, 0)[0].Value = component['cid']
                        aname1_node.Elements(0).Value = component['name']
                        casn_node.Elements(0).Value = component['cas_number']
                        print(f"添加组分成功:{component['name']}")
                print("成功添加组分")
            except Exception as e:
                print(f"在添加组分时出错: {e}")
                raise

            # 处理亨利组分
            try:
                henry_components = config.get('henry_components', {})
                if henry_components:
                    print("开始设置亨利组分...")
                    # 确保Henry-Comps目录存在
                    henry_comps_path = r"\Data\Components\Henry-Comps"
                    henry_comps_node = self.aspen.Tree.FindNode(henry_comps_path)
                    if not henry_comps_node:
                        # 如果目录不存在，可能需要创建
                        components_node = self.aspen.Tree.FindNode(r"\Data\Components")
                        components_node.Elements.Add("Henry-Comps")
                    # 遍历所有Henry组分集
                    for henry_set, hc_data in henry_components.items():
                        # 创建或获取Henry组分集
                        henry_set_path = fr"{henry_comps_path}\{henry_set}"
                        henry_set_node = self.aspen.Tree.FindNode(henry_set_path)
                        if not henry_set_node:
                            henry_comps_node.Elements.Add(henry_set)
                        # 确保Input和CID目录存在
                        cid_path = fr"{henry_set_path}\Input\CID"
                        cid_node_path = self.aspen.Tree.FindNode(cid_path)
                        if not cid_path:
                            print("目录不存在...")
                        # 添加组分
                        for i, component in enumerate(hc_data.get('components', [])):
                            # 创建CID节点
                            cid_node_path.Elements.InsertRow(0, 0)
                            # 设置CID节点的值
                            cid_node_path.Elements(0).Value = component.get('formula', '')
                    print(f"成功设置 {len(henry_components)} 个Henry组分集")
            except Exception as e:
                print(f"在处理亨利组分时出错: {e}")
            # print("components配置已成功写入Aspen模拟文件")
        except Exception as e:
            print(f"写入components配置时出错: {e}")
            raise

    def write_property_methods_to_aspen(self, config: Dict[str, Any]):
        """
        将配置写入Aspen模拟文件
        """
        # 添加物性方法
        try:
            property_methods_node = self.aspen.Tree.FindNode(r"\Data\Properties\Property Methods")
            # 找到基本的物性方法
            basis_method = None
            for i, method_data in enumerate(config.get('property_methods', [])):
                if method_data.get('is_basis_method', True):
                    basis_method = method_data['method_name']
                    GBASEOPSET_node = self.aspen.Tree.FindNode(r"\Data\Properties\Specifications\Input\GBASEOPSET")
                    GBASEOPSET_node.Value = basis_method
                    GOPSETNAME_node = self.aspen.Tree.FindNode(r"\Data\Properties\Specifications\Input\GOPSETNAME")
                    GOPSETNAME_node.Value = basis_method
                    GPPROCTYPE_node = self.aspen.Tree.FindNode(r"\Data\Properties\Specifications\Input\GPPROCTYPE")
                    GPPROCTYPE_node.Value = "ALL"
                print(f"成功设置property_methods: {basis_method}")
        except Exception as e:
            print(f"在设置property_methods时出错: {e}")
            raise
    def write_blocks_to_aspen(self, config: Dict[str, Any]):
        """
        将配置写入Aspen模拟文件
        """
        # 添加模块blocks
        try:
            blocks_node = self.aspen.Tree.FindNode(r"\Data\Blocks")
            for i, blocks in enumerate(config.get('blocks', [])):
                print(f"开始添加blocks:{blocks['name']}!{blocks['type']}")
                blocks_node.Elements.Add(f"{blocks['name']}!{blocks['type']}")
                print(f"添加blocks成功:{blocks['name']}!{blocks['type']}")
            print("成功添加blocks")
        except Exception as e:
            print(f"在添加blocks时出错: {e}")
            raise

    def write_stream_to_aspen(self, config: Dict[str, Any]):
        """
        将配置写入Aspen模拟文件
        """
        # 添加物流streams
        try:
            streams_node = self.aspen.Tree.FindNode(r"\Data\Streams")
            for i, streams in enumerate(config.get('streams', [])):
                streams_node.Elements.Add(f"{streams}")
                print(f"添加streams成功: {streams}")
            print("成功添加streams")
        except Exception as e:
            print(f"在添加streams时出错: {e}")
            raise

    def write_block_connections_to_aspen(self, config: Dict[str, Any]):
        """
        将配置写入Aspen模拟文件
        """
        # 添加连接
        try:
            blocks_node = self.aspen.Tree.FindNode(r"\Data\Blocks")
            for block_name, connection_data in config.get('block_connections', {}).items():
                for streams, type in connection_data.items():
                    blocks_node.Elements(block_name).Elements("Ports").Elements(type).Elements.Add(streams)
            print("成功添加block_connections")
        except Exception as e:
            print(f"在添加block_connections时出错: {e}")
            raise
    def write_stream_data_to_aspen(self, config: Dict[str, Any]):
        """
        将stream_data配置写入Aspen模拟文件
        """
        try:
            for stream, stream_data_detail in config.get('stream_data', {}).items():
                MIXED_SPEC_NODE = self.aspen.Tree.FindNode(fr"\Data\Streams\{stream}\Input\MIXED_SPEC\MIXED")
                self.add_if_not_empty(stream_data_detail, MIXED_SPEC_NODE, "MIXED_SPEC")
                PRES_NODE = self.aspen.Tree.FindNode(fr"\Data\Streams\{stream}\Input\PRES\MIXED")
                TEMP_NODE = self.aspen.Tree.FindNode(fr"\Data\Streams\{stream}\Input\TEMP\MIXED")
                VFRAC_NODE = self.aspen.Tree.FindNode(fr"\Data\Streams\{stream}\Input\VFRAC\MIXED")
                if stream_data_detail["MIXED_SPEC"] == "TP":
                    if 'pressure' in stream_data_detail:
                        if stream_data_detail["pressure"]["PRES_VALUE"] is not None:
                            PRES_NODE.SetValueAndUnit(stream_data_detail["pressure"]["PRES_VALUE"], self.convert_unitstr(stream_data_detail["pressure"]["PRES_UNITS"]))
                        if stream_data_detail["temperature"]["TEMP_VALUE"] is not None:
                            TEMP_NODE.SetValueAndUnit(stream_data_detail["temperature"]["TEMP_VALUE"], self.convert_unitstr(stream_data_detail["temperature"]["TEMP_UNITS"]))
                elif stream_data_detail["MIXED_SPEC"] == "TV":
                    self.add_if_not_empty(stream_data_detail["temperature"], TEMP_NODE, "TEMP_VALUE", "TEMP_UNITS")
                    self.add_if_not_empty(stream_data_detail["vfrac"], VFRAC_NODE, "VFRAC_VALUE")
                elif stream_data_detail["MIXED_SPEC"] == "PV":
                    self.add_if_not_empty(stream_data_detail["pressure"], PRES_NODE, "PRES_VALUE", "PRES_UNITS")
                    self.add_if_not_empty(stream_data_detail["vfrac"], VFRAC_NODE, "VFRAC_VALUE")
                if "flow" in stream_data_detail:
                    flow_nodes = self.aspen.Tree.FindNode(fr"\Data\Streams\{stream}\Input\FLOW\MIXED") # 规定-组分流量
                    FLOWBASE_NODE = self.aspen.Tree.FindNode(fr"\Data\Streams\{stream}\Input\FLOWBASE\MIXED")  # 规定-总流量-基准
                    TOTFLOW_NODE = self.aspen.Tree.FindNode(fr"\Data\Streams\{stream}\Input\TOTFLOW\MIXED")  # 规定-总流量
                    BASIS_NODE = self.aspen.Tree.FindNode(fr"\Data\Streams\{stream}\Input\BASIS\MIXED")  # 规定-组成-基准
                    self.add_if_not_empty(stream_data_detail["flow"], FLOWBASE_NODE, "FLOWBASE")
                    self.add_if_not_empty(stream_data_detail["flow"], TOTFLOW_NODE, "TOTFLOW_VALUE", "TOTFLOW_UNITS","FLOWBASE")
                    self.add_if_not_empty(stream_data_detail["flow"], BASIS_NODE, "BASIS")
                    for i, components in enumerate(config.get('components', [])):
                        comp = components['cid']
                        if comp in stream_data_detail["flow"]:
                            # comp_flow = stream_data_detail["flow"][comp]
                            # flow_nodes.Elements(comp).Value = comp_flow['FLOW_VALUE']
                            self.add_if_not_empty(stream_data_detail["flow"][comp], flow_nodes.Elements(comp), "FLOW_VALUE", "FLOW_UNITS","FLOW_BASIS")
                print(f"成功添加{stream}的stream_data")
            print("成功添加stream_data")
        except Exception as e:
            print(f"在添加stream_data时出错: {e}")
            raise

    def add_if_not_empty(self, data_dict, node, value_key, unit_key=None, basis_key=None):
        """如果值不为空，则将其添加到字典中"""
        if value_key in data_dict and unit_key in data_dict and data_dict[
            value_key] is not None and basis_key is not None:
            node.SetValueUnitAndBasis(data_dict[value_key], self.convert_unitstr(data_dict[unit_key]),
                                      data_dict[basis_key])
        elif value_key in data_dict and unit_key in data_dict and data_dict[value_key] is not None:
            node.SetValueAndUnit(data_dict[value_key], self.convert_unitstr(data_dict[unit_key]))
        elif value_key in data_dict and data_dict[value_key] is not None and unit_key is None:
            node.Value = data_dict[value_key]

    def write_reactions_data_to_aspen(self, config: Dict[str, Any]):
        """
        将reactions_data配置写入Aspen模拟文件
        """
        try:
            for reaction, reactions_data in config.get('reactions', {}).items():
                REAC_NODE = self.aspen.Tree.FindNode(fr"\Data\Reactions\Reactions")  # 反应-化学计量-反应物
                REAC_NODE.Elements.Add(f"{reaction}!{reactions_data['type']}")
                # COEF_NODE = self.aspen.Tree.FindNode(fr"\Data\Reactions\Reactions\{reaction}\Input\COEF")  # 反应-化学计量-反应物
                # 反应编号问题解决后添加
            print(f"成功添加reactions_data")
        except Exception as e:
            print(f"在添加reactions_data时出错: {e}")
            raise

    def write_convergence_data_to_aspen(self, config: Dict[str, Any]):
        """
        将convergence_data配置写入Aspen模拟文件
        """
        try:
            conv_options = config.get("convergence", {}).get("conv_options", {})
            TEAR_METHOD_NODE = self.aspen.Tree.FindNode(fr"\Data\Convergence\Conv-Options\Input\TEAR_METHOD")  # 收敛-选项-默认方法
            WEG_MAXIT_NOD = self.aspen.Tree.FindNode(fr"\Data\Convergence\Conv-Options\Input\WEG_MAXIT")  # 收敛-选项-迭代次数
            self.add_if_not_empty(conv_options, TEAR_METHOD_NODE, "tear_method")
            self.add_if_not_empty(conv_options, WEG_MAXIT_NOD, "weg_maxit")
            #TEAR_COMPS_NODES = self.aspen.Tree.FindNode(fr"\Data\Convergence\Tear\Input\COMPS")
            TEAR_TOL_NODES = self.aspen.Tree.FindNode(fr"\Data\Convergence\Tear\Input\TOL")
            # 撕裂数据
            tear_data = config.get("convergence", {}).get("tear_data", [])
            for i, tear_streams in enumerate(tear_data):
                tear_stream_name = tear_streams["tear_stream_name"]
                TEAR_TOL_NODES.Elements.InsertRow(0, 0)
                TEAR_TOL_NODES.Elements.LabelNode(0, 0)[0].Value = tear_stream_name
                TEAR_TOL_NODES.Elements(0).Value = tear_streams["tear_stream_tol"]
            # # 计算顺序数据
            # seq_data = config.get("convergence", {}).get("seq_data", [])
            # SEQ_NODES = self.aspen.Tree.FindNode(fr"\Data\Convergence\Sequence")  # 收敛-序列
            # for i, seq in enumerate(seq_data):
            #     seq_name = seq["sep_name"]
            #     sep_type = seq["sep_type"] # 无需添加
            #     SEQ_NODES.Elements.Add(seq_name)
            #     BLOCK_ID_NODES = self.aspen.Tree.FindNode(fr"\Data\Convergence\Sequence\{seq_name}\Input\BLOCK_ID")  # 序列-计算顺序-模块
            #     BLOCK_TYPE_NODES = self.aspen.Tree.FindNode(fr"\Data\Convergence\Sequence\{seq_name}\Input\BLOCK_TYPE")  # 序列-计算顺序-模块
            #     calc_seq_data = seq["calc_seq"]
            #     for num, calc_seq in enumerate(calc_seq_data):
            #         calc_seq_num = calc_seq["seq"]
            #         block_id = calc_seq["block_id"]
            #         block_type = calc_seq["block_type"]
            #         print(block_id)
            #         BLOCK_TYPE_NODES.Elements.InsertRow(0, num)
            #         BLOCK_TYPE_NODES.Elements(num).Value = block_type
            #         BLOCK_ID_NODES.Elements(num).Value = block_id
            # # 收敛-收敛数据
            # conv_data = config.get("convergence", {}).get("conv_data", [])
            # CONV_NODES = self.aspen.Tree.FindNode(fr"\Data\Convergence\Convergence")  # 收敛节点
            # for i, conv in enumerate(conv_data):
            #     conv_name = conv["conv_name"]
            #     CONV_NODES.Elements.Add(conv_name)
            print(f"成功添加convergence_data")
        except Exception as e:
            print(f"在添加convergence_data时出错: {e}")
            raise

    def write_design_specs_data_to_aspen(self, config: Dict[str, Any]):
        """
        将设计规定配置写入Aspen模拟文件
        """
        try:
            # 获取设计规定配置
            design_specs_config = config.get('design_specs', {})
            for spec_name, spec_data in design_specs_config.items():
                print(f"开始写入设计规定: {spec_name}")
                Design_Spec_NODE = self.aspen.Tree.FindNode(fr"\Data\Flowsheeting Options\Design-Spec")
                Design_Spec_NODE.Elements.Add(spec_name)
                base_path = fr"\Data\Flowsheeting Options\Design-Spec\{spec_name}\Input"
                fvn_variable_node = self.aspen.Tree.FindNode(fr"{base_path}\FVN_VARIABLE")

                # 2. 写入采样变量 (FVN_*系列)
                sampled_var = spec_data.get("sampled_variables", [])
                for i, sampled_var_data in enumerate(sampled_var):
                    sampled_var_name = sampled_var_data["variable_name"]
                    fvn_variable_node.Elements.InsertRow(0, 0)
                    fvn_variable_node.Elements.LabelNode(0, 0)[0].Value = sampled_var_name
                    # 写入采样变量引用参数（模型工具，物性参数，反应暂不支持）
                    opt_categ_node = self.aspen.Tree.FindNode(fr"{base_path}\OPT_CATEG\{sampled_var_name}") #类别
                    self.add_if_not_empty(sampled_var_data, opt_categ_node, f"opt_categ")
                    variable_type_node = self.aspen.Tree.FindNode(fr"{base_path}\FVN_VARTYPE\{sampled_var_name}") #类型
                    block_node = self.aspen.Tree.FindNode(fr"{base_path}\FVN_BLOCK\{sampled_var_name}") #模块
                    variable_node = self.aspen.Tree.FindNode(fr"{base_path}\FVN_VARIABLE\{sampled_var_name}") #变量
                    sentence_node = self.aspen.Tree.FindNode(fr"{base_path}\FVN_SENTENCE\{sampled_var_name}") #语句
                    units_node = self.aspen.Tree.FindNode(fr"{base_path}\FVN_UOM\{sampled_var_name}") #单位
                    stream_node = self.aspen.Tree.FindNode(fr"{base_path}\FVN_STREAM\{sampled_var_name}") #流股
                    substream_node = self.aspen.Tree.FindNode(fr"{base_path}\FVN_SUBS\{sampled_var_name}") #子流股
                    component_node = self.aspen.Tree.FindNode(fr"{base_path}\FVN_COMPONEN\{sampled_var_name}") #组分
                    # fvn_params = ["variable_type", "stream", "block", "variable", "component", "substream", "variable_type", "units", "sentence"]
                    fvn_params_node = [
                        (variable_type_node, "variable_type"),
                        (block_node, "block"),
                        (variable_node, "variable"),
                        (stream_node, "stream"),
                        (substream_node, "substream"),
                        (component_node, "component"),
                        (sentence_node, "sentence"),
                        (units_node, "units")
                    ]
                    for node, key in fvn_params_node:
                        if key in sampled_var_data and node is not None:
                            self.add_if_not_empty(sampled_var_data, node, f"{key}")
                            # self.add_if_not_empty(sampled_var_data, opt_categ_node, f"opt_categ")
                            # self.add_if_not_empty(sampled_var_data, variable_type_node, f"variable_type")
                            # self.add_if_not_empty(sampled_var_data, block_node, f"block")
                            # self.add_if_not_empty(sampled_var_data, variable_node, f"variable")
                            # self.add_if_not_empty(sampled_var_data, sentence_node, f"sentence")
                            # self.add_if_not_empty(sampled_var_data, units_node, f"units")
                            # self.add_if_not_empty(sampled_var_data, stream_node, f"stream")
                            # self.add_if_not_empty(sampled_var_data, substream_node, f"substream")
                            # self.add_if_not_empty(sampled_var_data, component_node, f"component")

                # 3. 写入目标函数配置
                objective_function = spec_data.get("objective_function", {})
                expr1_node = self.aspen.Tree.FindNode(fr"{base_path}\EXPR1")
                tol_node = self.aspen.Tree.FindNode(fr"{base_path}\TOL")
                expr2_node = self.aspen.Tree.FindNode(fr"{base_path}\EXPR2")
                self.add_if_not_empty(objective_function, expr1_node, f"EXPR1")
                self.add_if_not_empty(objective_function, tol_node, f"TOL")
                self.add_if_not_empty(objective_function, expr2_node, f"EXPR2")

                # 4. 写入操纵变量 (VARY_*系列)
                manipulated_variables = spec_data.get("manipulated_variables", [])
                for i, manipulated_var_data in enumerate(manipulated_variables):
                    variable_type_node = self.aspen.Tree.FindNode(fr"{base_path}\VARY_VARTYPE")
                    block_node = self.aspen.Tree.FindNode(fr"{base_path}\VARYBLOCK")
                    variable_name_node = self.aspen.Tree.FindNode(fr"{base_path}\VARYVARIABLE")
                    sentence_node = self.aspen.Tree.FindNode(fr"{base_path}\VARYSENTENCE")
                    units_node = self.aspen.Tree.FindNode(fr"{base_path}\VARYUOM")
                    self.add_if_not_empty(manipulated_var_data, variable_type_node, f"variable_type")
                    self.add_if_not_empty(manipulated_var_data, block_node, f"block")
                    self.add_if_not_empty(manipulated_var_data, variable_name_node, f"variable_name")
                    self.add_if_not_empty(manipulated_var_data, sentence_node, f"sentence")
                    self.add_if_not_empty(manipulated_var_data, units_node, f"units")
                    # 写入VARYLINE1-4
                    for line_num in range(1, 5):
                        line_key = f"line{line_num}"
                        if line_key in manipulated_var_data:
                            line_value = manipulated_var_data[line_key]
                            node_name = f"VARYLINE{line_num}"
                            node = self.aspen.Tree.FindNode(fr"{base_path}\{node_name}")
                            node.Value = line_value

                # 4. 写入操纵变量限制
                bounds = spec_data.get("bounds", {})
                upper_node = self.aspen.Tree.FindNode(fr"{base_path}\UPPER") #上界
                lower_node = self.aspen.Tree.FindNode(fr"{base_path}\LOWER") #下界
                step_size_node = self.aspen.Tree.FindNode(fr"{base_path}\STEP_SIZE") #步长
                max_step_size_node = self.aspen.Tree.FindNode(fr"{base_path}\MAX_STEP_SIZ") #最大步长
                self.add_if_not_empty(bounds, lower_node, f"LOWER")
                self.add_if_not_empty(bounds, upper_node, f"UPPER")
                self.add_if_not_empty(bounds, step_size_node, f"STEP_SIZE")
                self.add_if_not_empty(bounds, max_step_size_node, f"MAX_STEP_SIZ")




                #
                # # 5. 写入边界和步长设置
                # bounds = spec_data.get("bounds", {})
                #
                # # 写入下界
                # if "LOWER" in bounds:
                #     lower_value = bounds["LOWER"]
                #     lower_node = self.aspen.Tree.FindNode(fr"{base_path}\LOWER")
                #     if lower_node is not None and lower_value is not None:
                #         lower_node.Value = lower_value
                #         print(f"  写入LOWER: {lower_value}")
                #
                # # 写入上界
                # if "UPPER" in bounds:
                #     upper_value = bounds["UPPER"]
                #     upper_node = self.aspen.Tree.FindNode(fr"{base_path}\UPPER")
                #     if upper_node is not None and upper_value is not None:
                #         upper_node.Value = upper_value
                #         print(f"  写入UPPER: {upper_value}")
                #
                # # 写入步长
                # if "STEP_SIZE" in bounds:
                #     step_size_value = bounds["STEP_SIZE"]
                #     step_size_node = self.aspen.Tree.FindNode(fr"{base_path}\STEP_SIZE")
                #     if step_size_node is not None and step_size_value is not None:
                #         step_size_node.Value = step_size_value
                #         print(f"  写入STEP_SIZE: {step_size_value}")
                #
                # # 写入最大步长
                # if "MAX_STEP_SIZ" in bounds:
                #     max_step_size_value = bounds["MAX_STEP_SIZ"]
                #     max_step_size_node = self.aspen.Tree.FindNode(fr"{base_path}\MAX_STEP_SIZ")
                #     if max_step_size_node is not None and max_step_size_value is not None:
                #         max_step_size_node.Value = max_step_size_value
                #         print(f"  写入MAX_STEP_SIZ: {max_step_size_value}")
                #
                # # 写入阈值
                # if "THRESHOLD" in bounds:
                #     threshold_value = bounds["THRESHOLD"]
                #     threshold_node = self.aspen.Tree.FindNode(fr"{base_path}\THRESHOLD")
                #     if threshold_node is not None and threshold_value is not None:
                #         threshold_node.Value = threshold_value
                #         print(f"  写入THRESHOLD: {threshold_value}")

                print(f"  设计规定 '{spec_name}' 写入完成")

            print("所有设计规定配置写入完成")

        except Exception as e:
            print(f"写入设计规定配置时出错: {e}")
            import traceback
            traceback.print_exc()
            raise

    def write_blocks_Mixer_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_Mixer_data配置写入Aspen模拟文件
        """
        try:
            for block, Mixer_data in config.get('blocks_Mixer_data', {}).items():
                PRES_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PRES")  # 闪蒸选项-压力
                T_EST_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\T_EST")  # 闪蒸选项-温度估值
                MIXIT_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\MIXIT")  # 闪蒸选项-最大迭代次数
                TOL_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\TOL")  # 闪蒸选项-容许误差
                self.add_if_not_empty(Mixer_data["SPEC_DATA"], PRES_NODE, "PRES_VALUE", "PRES_UNITS")
                self.add_if_not_empty(Mixer_data["SPEC_DATA"], T_EST_NODE, "T_EST_VALUE", "T_EST_UNITS")
                self.add_if_not_empty(Mixer_data["SPEC_DATA"], MIXIT_NODE, "MIXIT")
                self.add_if_not_empty(Mixer_data["SPEC_DATA"], TOL_NODE, "TOL", )
            print(f"成功添加blocks_Mixer_data")
        except Exception as e:
            print(f"在添加blocks_Mixer_data时出错: {e}")
            raise

    def write_blocks_Valve_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_Valve_data配置写入Aspen模拟文件
        """
        try:
            for block, Valve_data in config.get('blocks_Valve_data', {}).items():
                MODE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\MODE")  # 作业-计算类型
                self.add_if_not_empty(Valve_data["JOB_DATA"], MODE_NODE, "MODE")
                if Valve_data["JOB_DATA"]["MODE"] == "ADIAB-FLASH":  # 当前只抽取指定出口压力下绝热闪蒸，可自行添加
                    P_OUT_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\P_OUT")  # 作业-压力规范-出口压力
                    NPHASE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\NPHASE")  # 作业-闪蒸选项-有效相态
                    FLASH_MAXIT_NODE = self.aspen.Tree.FindNode(
                        fr"\Data\Blocks\{block}\Input\FLASH_MAXIT")  # 作业-闪蒸选项-最大迭代次数
                    FLASH_TOL_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\FLASH_TOL")  # 作业-闪蒸选项-容许误差
                    self.add_if_not_empty(Valve_data["JOB_DATA"], P_OUT_NODE, "P_OUT_VALUE", "P_OUT_UNITS")
                    self.add_if_not_empty(Valve_data["JOB_DATA"], NPHASE_NODE, "NPHASE")
                    self.add_if_not_empty(Valve_data["JOB_DATA"], FLASH_MAXIT_NODE, "FLASH_MAXIT")
                    self.add_if_not_empty(Valve_data["JOB_DATA"], FLASH_TOL_NODE, "FLASH_TOL", )
            print(f"成功添加blocks_Value_data")
        except Exception as e:
            print(f"在添加blocks_Value_data时出错: {e}")
            raise

    def write_blocks_Compr_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_Compr_data配置写入Aspen模拟文件
        """
        try:
            for block, Compr_data in config.get('blocks_Compr_data', {}).items():
                MODEL_TYPE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\MODEL_TYPE")  # 规定-模型
                TYPE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\TYPE")  # 规定-类型
                OPT_SPEC_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\OPT_SPEC")  # 规定-出口规范
                PRES_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PRES")  # 规定-排放压力
                # UTILITY_ID_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\UTILITY_ID")  # 公用工程--暂不添加
                self.add_if_not_empty(Compr_data["SPEC_DATA"], MODEL_TYPE_NODE, "MODEL_TYPE")
                self.add_if_not_empty(Compr_data["SPEC_DATA"], TYPE_NODE, "TYPE", )
                self.add_if_not_empty(Compr_data["SPEC_DATA"], OPT_SPEC_NODE, "OPT_SPEC")
                self.add_if_not_empty(Compr_data["SPEC_DATA"], PRES_NODE, "PRES_VALUE", "PRES_UNITS")
                # self.add_if_not_empty(Compr_data["SPEC_DATA"], UTILITY_ID_NODE, "UTILITY_ID")
            print(f"成功添加blocks_Compr_data")
        except Exception as e:
            print(f"在添加blocks_Compr_data时出错: {e}")
            raise

    def write_blocks_Heater_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_Heater_data配置写入Aspen模拟文件
        """
        try:
            for block, Heater_data in config.get('blocks_Heater_data', {}).items():
                SPEC_OPT_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\SPEC_OPT")  # 规定-闪蒸计算类型
                TEMP_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\TEMP")  # 规定-温度
                DELT_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DELT")  # 规定-温度变化
                DEGSUP_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DEGSUP")  # 规定-过热度
                DEGSUB_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DEGSUB")  # 规定-过冷度
                VFRAC_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\VFRAC")  # 规定-汽相分率
                PRES_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PRES")  # 规定-压力
                DUTY_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DUTY")  # 规定-负载
                # UTILITY_ID_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\UTILITY_ID")  # 公用工程--暂不添加
                self.add_if_not_empty(Heater_data["SPEC_DATA"], TEMP_NODE, "TEMP_VALUE", "TEMP_UNITS")
                self.add_if_not_empty(Heater_data["SPEC_DATA"], DELT_NODE, "DELT_VALUE", "DELT_UNITS")
                self.add_if_not_empty(Heater_data["SPEC_DATA"], DEGSUP_NODE, "DEGSUP_VALUE", "DEGSUP_UNITS")
                self.add_if_not_empty(Heater_data["SPEC_DATA"], DEGSUB_NODE, "DEGSUB_VALUE", "DEGSUB_UNITS")
                self.add_if_not_empty(Heater_data["SPEC_DATA"], PRES_NODE, "PRES_VALUE", "PRES_UNITS")
                self.add_if_not_empty(Heater_data["SPEC_DATA"], DUTY_NODE, "DUTY_VALUE", "DUTY_UNITS")
                self.add_if_not_empty(Heater_data["SPEC_DATA"], VFRAC_NODE, "VFRAC_VALUE")
                self.add_if_not_empty(Heater_data["SPEC_DATA"], SPEC_OPT_NODE, "SPEC_OPT")
                # self.add_if_not_empty(Heater_data["SPEC_DATA"], UTILITY_ID_NODE, "UTILITY_ID")
            print(f"成功添加blocks_Heater_data")
        except Exception as e:
            print(f"在添加blocks_Heater_data时出错: {e}")
            raise

    def write_blocks_Pump_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_Pump_data配置写入Aspen模拟文件
        """
        try:
            for block, Pump_data in config.get('blocks_Pump_data', {}).items():
                PUMP_TYPE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PUMP_TYPE")  # 规定-模型
                OPT_SPEC_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\OPT_SPEC")  # 规定-出口规范
                PRES_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PRES")  # 规定-排放压力
                # UTILITY_ID_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\UTILITY_ID")  # 公用工程--暂不添加
                self.add_if_not_empty(Pump_data["SPEC_DATA"], PUMP_TYPE_NODE, "PUMP_TYPE")
                self.add_if_not_empty(Pump_data["SPEC_DATA"], OPT_SPEC_NODE, "OPT_SPEC")
                self.add_if_not_empty(Pump_data["SPEC_DATA"], PRES_NODE, "PRES_VALUE", "PRES_UNITS")
                # self.add_if_not_empty(Pump_data["SPEC_DATA"], UTILITY_ID_NODE, "UTILITY_ID")
            print(f"成功添加blocks_Pump_data")
        except Exception as e:
            print(f"在添加blocks_Pump_data时出错: {e}")
            raise

    def write_blocks_RStoic_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_RStoic_data配置写入Aspen模拟文件
        """
        try:
            for block, RStoic_data in config.get('blocks_RStoic_data', {}).items():
                # 规定提取
                SPEC_OPT_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\SPEC_OPT")  # 规定-闪蒸计算类型
                TEMP_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\TEMP")  # 规定-温度
                DELT_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DELT")  # 规定-温度变化
                VFRAC_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\VFRAC")  # 规定-汽相分率
                PRES_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PRES")  # 规定-压力
                DUTY_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DUTY")  # 规定-负载
                PHASE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PHASE")  # 规定-有效相态
                # UTILITY_ID_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\UTILITY_ID")  # 公用工程
                self.add_if_not_empty(RStoic_data["SPEC_DATA"], SPEC_OPT_NODE, "SPEC_OPT")
                self.add_if_not_empty(RStoic_data["SPEC_DATA"], TEMP_NODE, "TEMP_VALUE", "TEMP_UNITS")
                self.add_if_not_empty(RStoic_data["SPEC_DATA"], DELT_NODE, "DELT_VALUE", "DELT_UNITS")
                self.add_if_not_empty(RStoic_data["SPEC_DATA"], PRES_NODE, "PRES_VALUE", "PRES_UNITS")
                self.add_if_not_empty(RStoic_data["SPEC_DATA"], DUTY_NODE, "DUTY_VALUE", "DUTY_UNITS")
                self.add_if_not_empty(RStoic_data["SPEC_DATA"], VFRAC_NODE, "VFRAC_VALUE")
                self.add_if_not_empty(RStoic_data["SPEC_DATA"], PHASE_NODE, "PHASE_VALUE")
                # self.add_if_not_empty(RStoic_data["SPEC_DATA"], UTILITY_ID_NODE, "UTILITY_ID")
                # 反应提取
                SERIES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\SERIES")  # 反应-反应连续发生
                self.add_if_not_empty(RStoic_data["REAC_DATA"], SERIES, "SERIES")
                KEY_SSID_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\KEY_SSID")  # 反应-反应编号
                CONV_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\CONV") # 反应-转化率
                KEY_CID_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\KEY_CID")  # 反应-组分转化率
                OPT_EXT_CONV_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\OPT_EXT_CONV")  # 反应-规范类型
                EXTENT_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\EXTENT")  # 反应-摩尔反应进度
                COEF_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\COEF")  # 反应-化学计量-反应物
                COEF1_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\COEF1")  # 反应-化学计量-反应物
                for i, reac_data in enumerate(RStoic_data["REAC_DATA"]["REAC"]):
                    KEY_SSID_NODE.Elements.InsertRow(0, 0)
                    CONV_NODE.Elements.InsertRow(0, 0)
                    KEY_CID_NODE.Elements.InsertRow(0, 0)
                    OPT_EXT_CONV_NODE.Elements.InsertRow(0, 0)
                    EXTENT_NODE.Elements.InsertRow(0, 0)
                    COEF_NODE.Elements.InsertRow(0, 0)
                    COEF1_NODE.Elements.InsertRow(0, 0)
                    reac_id = reac_data["KEY_SSID"]
                    KEY_SSID_NODE.Elements.LabelNode(0, 0)[0].Value = reac_id
                    CONV_NODE.Elements.LabelNode(0, 0)[0].Value = reac_id
                    KEY_CID_NODE.Elements.LabelNode(0, 0)[0].Value = reac_id
                    OPT_EXT_CONV_NODE.Elements.LabelNode(0, 0)[0].Value = reac_id
                    EXTENT_NODE.Elements.LabelNode(0, 0)[0].Value = reac_id
                    COEF_NODE.Elements.LabelNode(0, 0)[0].Value = reac_id
                    COEF1_NODE.Elements.LabelNode(0, 0)[0].Value = reac_id
                    CONV = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\CONV\{reac_id}")  # 反应-转化率
                    KEY_CID = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\KEY_CID\{reac_id}")  # 反应-组分转化率
                    OPT_EXT_CONV = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\OPT_EXT_CONV\{reac_id}")  # 反应-规范类型
                    EXTENT = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\EXTENT\{reac_id}")  # 反应-摩尔反应进度
                    self.add_if_not_empty(reac_data, CONV, "CONV")
                    self.add_if_not_empty(reac_data, KEY_CID, "KEY_CID")
                    self.add_if_not_empty(reac_data, OPT_EXT_CONV, "OPT_EXT_CONV")
                    self.add_if_not_empty(reac_data, EXTENT, "EXTENT")
                    COEF_MIX_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\COEF\{reac_id}")  # 反应-化学计量-反应物
                    for cofe_mix, cofe_value in reac_data.get('COEF_DATA', {}).items():
                        COEF_MIX_NODE.Elements.InsertRow(0, 0)
                        COEF_MIX_NODE.Elements.LabelNode(0, 0)[0].Value = cofe_mix
                        COEF_MIX_NODE.Elements(0, 0).Value = cofe_value
                    COEF1_MIX_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\COEF1\{reac_id}")  # 反应-化学计量-反应物
                    for cofe1_mix, cofe1_value in reac_data.get('COEF1_DATA', {}).items():
                        COEF1_MIX_NODE.Elements.InsertRow(0, 0)
                        COEF1_MIX_NODE.Elements.LabelNode(0, 0)[0].Value = cofe1_mix
                        COEF1_MIX_NODE.Elements(0, 0).Value = cofe1_value
            print(f"成功添加blocks_RStoic_data")
        except Exception as e:
            print(f"在添加blocks_RStoic_data时出错: {e}")
            raise

    def write_blocks_RPlug_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_RPlug_data配置写入Aspen模拟文件
        """
        try:
            for block, RPlug_data in config.get('blocks_RPlug_data', {}).items():
                # 添加规定
                TYPE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\TYPE")  # 规定-反应器类型
                OPT_TSPEC_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\OPT_TSPEC")  # 规定-操作条件
                self.add_if_not_empty(RPlug_data["SPEC_DATA"], TYPE_NODE, "TYPE")
                self.add_if_not_empty(RPlug_data["SPEC_DATA"], OPT_TSPEC_NODE, "OPT_TSPEC")
                if RPlug_data["SPEC_DATA"]["OPT_TSPEC"] == "CONST-TEMP":
                    REAC_TEMP_NODE = self.aspen.Tree.FindNode(
                        fr"\Data\Blocks\{block}\Input\REAC_TEMP")  # 规定-反应器类型-操作条件-指定反应器温度
                    self.add_if_not_empty(RPlug_data["SPEC_DATA"], REAC_TEMP_NODE, "REAC_TEMP")
                if RPlug_data["SPEC_DATA"]["OPT_TSPEC"] == "TEMP-PROF":
                    SPEC_TEMP_NODE = self.aspen.Tree.FindNode(
                        fr"\Data\Blocks\{block}\Input\SPEC_TEMP")  # 规定-反应器类型-操作条件-温度分布-温度
                    SPEC_TEMP_SUBNODES = self.get_child_nodes(
                        fr"\Data\Blocks\{block}\Input\SPEC_TEMP")  # 规定-反应器类型-操作条件-温度分布-温度
                    for i, SPEC_TEMP in SPEC_TEMP_SUBNODES:
                        SPEC_TEMP_NODE.Elements.InsertRow(0, i)
                        SPEC_TEMP_NODE.Elements.Elements(i).SetValueAndUnit(
                            RPlug_data["SPEC_DATA"][SPEC_TEMP]["SPEC_TEMP_VALUE"],
                            RPlug_data["SPEC_DATA"][SPEC_TEMP]["SPEC_TEMP_UNITS"])
                # 添加配置
                CHK_NTUBE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\CHK_NTUBE")  # 配置-多管反应器
                NTUBE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\NTUBE")  # 配置-多管反应器-管数
                LENGTH_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\LENGTH")  # 配置-反应器维度-长度
                DIAM_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DIAM")  # 配置-反应器维度-直径
                PHASE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PHASE")  # 配置-有效相-工艺流股
                self.add_if_not_empty(RPlug_data["CONFIG_DATA"], CHK_NTUBE_NODE, "CHK_NTUBE")
                self.add_if_not_empty(RPlug_data["CONFIG_DATA"], LENGTH_NODE, "LENGTH")
                self.add_if_not_empty(RPlug_data["CONFIG_DATA"], DIAM_NODE, "DIAM")
                self.add_if_not_empty(RPlug_data["CONFIG_DATA"], PHASE_NODE, "PHASE")
                self.add_if_not_empty(RPlug_data["CONFIG_DATA"], NTUBE_NODE, "NTUBE")
                # 添加反应
                REACSYS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\REACSYS")  # 反应-反应体系
                self.add_if_not_empty(RPlug_data["REAC_DATA"], REACSYS_NODE, "REACSYS")
                RXN_ID_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\RXN_ID")  # 反应-所选反应集
                for RXN_ID, RXN_ID_DATA in RPlug_data["REAC_DATA"].get('RXN_ID', {}).items():
                    RXN_ID_NODES.Elements.InsertRow(0, 0)
                    RXN_ID_NODES.Elements(0).Value = RXN_ID_DATA
                # 添加压力
                PRES_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PRES")  # 压力-进口压力
                OPT_PDROP_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\OPT_PDROP ")  # 压力-通过反应器的压降
                PDROP_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PDROP ")  # 压力-压降-工艺流股
                ROUGHNESS_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\ROUGHNESS ")  # 压力-摩擦关联式-粗糙度
                DP_FCOR_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DP_FCOR")  # 压力-摩擦关联式-压降关联式
                DP_MULT_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DP_MULT")  # 压力-摩擦关联式-压降比例因子
                self.add_if_not_empty(RPlug_data["PRES_DATA"], PRES_NODES, "PRES_VALUE", "PRES_UNITS")
                self.add_if_not_empty(RPlug_data["PRES_DATA"], OPT_PDROP_NODES, "OPT_PDROP")
                self.add_if_not_empty(RPlug_data["PRES_DATA"], PDROP_NODES, "PDROP_VALUE", "PDROP_UNITS")
                self.add_if_not_empty(RPlug_data["PRES_DATA"], ROUGHNESS_NODES, "ROUGHNESS_VALUE", "ROUGHNESS_UNITS")
                self.add_if_not_empty(RPlug_data["PRES_DATA"], DP_FCOR_NODES, "DP_FCOR")
                self.add_if_not_empty(RPlug_data["PRES_DATA"], DP_MULT_NODES, "DP_MULT")
                # 添加催化剂
                CAT_PRESENT_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\CAT_PRESENT")  # 催化剂-反应器内的催化剂
                IGN_CAT_VOL_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\IGN_CAT_VOL")  # 催化剂-忽略催化器体积
                BED_VOIDAGE_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\BED_VOIDAGE")  # 催化剂-规定-床空隙率
                CAT_RHO_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\CAT_RHO")  # 催化剂-规定-颗粒密度
                CATWT_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\CATWT")  # 催化剂-规定-催化剂装填
                self.add_if_not_empty(RPlug_data["CAT_DATA"], CAT_PRESENT_NODES, "CAT_PRESENT")
                self.add_if_not_empty(RPlug_data["CAT_DATA"], IGN_CAT_VOL_NODES, "IGN_CAT_VOL")
                self.add_if_not_empty(RPlug_data["CAT_DATA"], BED_VOIDAGE_NODES, "BED_VOIDAGE")
                self.add_if_not_empty(RPlug_data["CAT_DATA"], CAT_RHO_NODES, "CAT_RHO_VALUE", "CAT_RHO_UNITS")
                self.add_if_not_empty(RPlug_data["CAT_DATA"], CATWT_NODES, "CATWT_VALUE", "CATWT_UNITS")
            print(f"成功添加blocks_RPlug_data_data")
        except Exception as e:
            print(f"在添加blocks_RPlug_data_data时出错: {e}")
            raise

    def write_blocks_Flash2_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_Flash2_data配置写入Aspen模拟文件
        """
        try:
            for block, Flash2_data in config.get('blocks_Flash2_data', {}).items():
                SPEC_OPT_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\SPEC_OPT")  # 规定-闪蒸计算类型
                TEMP_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\TEMP")  # 规定-温度
                DELT_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DELT")  # 规定-温度变化
                VFRAC_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\VFRAC")  # 规定-汽相分率
                PRES_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PRES")  # 规定-压力
                DUTY_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DUTY")  # 规定-负载
                # UTILITY_ID_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\UTILITY_ID")  # 公用工程(放规定一起)
                self.add_if_not_empty(Flash2_data["SPEC_DATA"], TEMP_NODE, "TEMP_VALUE", "TEMP_UNITS")
                self.add_if_not_empty(Flash2_data["SPEC_DATA"], DELT_NODE, "DELT_VALUE", "DELT_UNITS")
                self.add_if_not_empty(Flash2_data["SPEC_DATA"], PRES_NODE, "PRES_VALUE", "PRES_UNITS")
                self.add_if_not_empty(Flash2_data["SPEC_DATA"], DUTY_NODE, "DUTY_VALUE", "DUTY_UNITS")
                self.add_if_not_empty(Flash2_data["SPEC_DATA"], VFRAC_NODE, "VFRAC_VALUE")
                # self.add_if_not_empty(Flash2_data["SPEC_DATA"], UTILITY_ID_NODE, "UTILITY_ID")
                self.add_if_not_empty(Flash2_data["SPEC_DATA"], SPEC_OPT_NODE, "SPEC_OPT")
            print(f"成功添加blocks_Flash2_data")
        except Exception as e:
            print(f"在添加blocks_Flash2_data时出错: {e}")
            raise
    def write_blocks_Decanter_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_Decanter_data配置写入Aspen模拟文件
        """
        try:
            for block, Decanter_data in config.get('blocks_Decanter_data', {}).items():
                TEMP_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\TEMP")  # 规定-倾析器规范-温度
                PRES_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PRES")  # 规定-倾析器规范-压力
                DUTY_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DUTY")  # 规定-倾析器规范-负荷
                self.add_if_not_empty(Decanter_data["SPEC_DATA"], TEMP_NODE, "TEMP_VALUE", "TEMP_UNITS")
                self.add_if_not_empty(Decanter_data["SPEC_DATA"], PRES_NODE, "PRES_VALUE", "PRES_UNITS")
                self.add_if_not_empty(Decanter_data["SPEC_DATA"], DUTY_NODE, "DUTY_VALUE", "DUTY_UNITS")
                L2_COMPS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\L2_COMPS")
                L2_CUTOFF_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\L2_CUTOFF")  # 规定-第二液相的组分摩尔分率
                L2_COMPS = Decanter_data["SPEC_DATA"]["L2_COMPS"]
                for num, comps in enumerate(L2_COMPS):
                    L2_COMPS_NODE.Elements.InsertRow(0, num)
                    L2_COMPS_NODE.Elements(num).Value = comps
                self.add_if_not_empty(Decanter_data["SPEC_DATA"], L2_CUTOFF_NODE, "L2_CUTOFF")
            print(f"成功添加blocks_Decanter_data")
        except Exception as e:
            print(f"在添加blocks_Decanter_data时出错: {e}")
            raise
    def write_blocks_Sep_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_Sep_data配置写入Aspen模拟文件
        """
        try:
            for block, Sep_data in config.get('blocks_Sep_data', {}).items():
                for FLOW, FLOW_DATA in Sep_data.get('SPEC_DATA', {}).items():
                    for i, COMP_DATA in enumerate(FLOW_DATA):
                        FLOWBASIS_NODE = self.aspen.Tree.FindNode(
                            fr"\Data\Blocks\{block}\Input\FLOWBASIS\{FLOW}\MIXED\{COMP_DATA['COMP_ID']}")  # 规定-出口流股条件-基准
                        FRACS_NODE = self.aspen.Tree.FindNode(
                            fr"\Data\Blocks\{block}\Input\FRACS\{FLOW}\MIXED\{COMP_DATA['COMP_ID']}")  # 规定-出口流股条件-规定-分流分率
                        FLOWS_NODE = self.aspen.Tree.FindNode(
                            fr"\Data\Blocks\{block}\Input\FLOWS\{FLOW}\MIXED\{COMP_DATA['COMP_ID']}")  # 规定-出口流股条件-规定-流量
                        self.add_if_not_empty(COMP_DATA, FLOWBASIS_NODE, "FLOWBASIS_VALUE")
                        self.add_if_not_empty(COMP_DATA, FRACS_NODE, "FRACS")
                        self.add_if_not_empty(COMP_DATA, FLOWS_NODE, "FLOWS")
            print(f"成功添加blocks_Sep_data")
        except Exception as e:
            print(f"在添加blocks_Sep_data时出错: {e}")
            raise

    def write_blocks_Sep2_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_Sep2_data配置写入Aspen模拟文件
        """
        try:
            for block, Sep2_data in config.get('blocks_Sep2_data', {}).items():
                for FLOW, FLOW_DATA in Sep2_data.get('SPEC_DATA', {}).items():
                    for i, COMP_DATA in enumerate(FLOW_DATA):
                        FLOWBASIS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\FLOWBASIS\MIXED\{FLOW}\{COMP_DATA['COMP_ID']}")  # 规定-出口流股条件-基准
                        FRACS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\FRACS\MIXED\{FLOW}\{COMP_DATA['COMP_ID']}")  # 规定-出口流股条件-规定-分流分率
                        FLOWS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\FLOWS\MIXED\{FLOW}\{COMP_DATA['COMP_ID']}")  # 规定-出口流股条件-规定-流量
                        self.add_if_not_empty(COMP_DATA, FLOWBASIS_NODE, "FLOWBASIS_VALUE")
                        self.add_if_not_empty(COMP_DATA, FRACS_NODE, "FRACS")
                        self.add_if_not_empty(COMP_DATA, FLOWS_NODE, "FLOWS")
            print(f"成功添加blocks_Sep2_data")
        except Exception as e:
            print(f"在添加blocks_Sep2_data时出错: {e}")
            raise

    def write_blocks_DSTWU_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_DSTWU_data配置写入Aspen模拟文件
        DSTWU: Distillation-Shortcut Waton-Underwood (精馏快捷计算)
        """
        try:
            for block, DSTWU_data in config.get('blocks_DSTWU_data', {}).items():
                spec_data = DSTWU_data.get("SPEC_DATA", {})

                # 塔规范参数
                OPT_NTRR_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\OPT_NTRR")  # 塔规范-选择RR或NSTAGE
                self.add_if_not_empty(spec_data, OPT_NTRR_NODE, "OPT_NTRR")

                # 根据OPT_NTRR的值选择设置RR或NSTAGE
                if "OPT_NTRR" in spec_data and spec_data["OPT_NTRR"] == "RR":
                    RR_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\RR")  # 塔规范-回流比
                    self.add_if_not_empty(spec_data, RR_NODE, "RR")
                elif "OPT_NTRR" in spec_data and spec_data["OPT_NTRR"] == "NSTAGE":
                    NSTAGE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\NSTAGE")  # 塔规范-塔板数
                    self.add_if_not_empty(spec_data, NSTAGE_NODE, "NSTAGE")

                # 压力
                PTOP_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PTOP")  # 压力-塔顶压力
                self.add_if_not_empty(spec_data, PTOP_NODE, "PTOP", "PTOP_UNITS")
                PBOT_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PBOT")  # 压力-塔底压力
                self.add_if_not_empty(spec_data, PBOT_NODE, "PBOT", "PBOT_UNITS")

                # 冷凝器规范
                OPT_RDV_NODE = self.aspen.Tree.FindNode(
                    fr"\Data\Blocks\{block}\Input\OPT_RDV")  # 冷凝器规范-选择LIQUID/VAPOR/VAPLIQ
                self.add_if_not_empty(spec_data, OPT_RDV_NODE, "OPT_RDV")

                # 当OPT_RDV为VAPLIQ时才设置RDV
                if "OPT_RDV" in spec_data and spec_data["OPT_RDV"] == "VAPLIQ":
                    RDV_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\RDV")  # 冷凝器规范-汽相分率
                    self.add_if_not_empty(spec_data, RDV_NODE, "RDV")

                # 关键组分回收率
                LIGHTKEY_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\LIGHTKEY")  # 关键组分-轻关键组分
                self.add_if_not_empty(spec_data, LIGHTKEY_NODE, "LIGHTKEY")

                RECOVH_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\RECOVH")  # 关键组分-重关键组分回收率
                self.add_if_not_empty(spec_data, RECOVH_NODE, "RECOVH")

                HEAVYKEY_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\HEAVYKEY")  # 关键组分-重关键组分
                self.add_if_not_empty(spec_data, HEAVYKEY_NODE, "HEAVYKEY")

                RECOVL_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\RECOVL")  # 关键组分-轻关键组分回收率
                self.add_if_not_empty(spec_data, RECOVL_NODE, "RECOVL")

            print(f"成功添加blocks_DSTWU_data")
        except Exception as e:
            print(f"在添加blocks_DSTWU_data时出错: {e}")
            raise

    def write_blocks_RadFrac_data_to_aspen(self, config: Dict[str, Any]):
        """
        将blocks_RadFrac_data配置写入Aspen模拟文件
        """
        try:
            for block, RadFrac_data in config.get('blocks_RadFrac_data', {}).items():
                # 添加配置
                CALC_MODE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\CALC_MODE")  # 配置-计算类型
                NSTAGE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\NSTAGE")  # 配置-塔板数
                CONDENSER_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\CONDENSER")  # 配置-冷凝器
                REBOILER_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\REBOILER")  # 配置-再沸器
                NO_PHASE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\NO_PHASE")  # 配置-有效相态
                BLKOPFREWAT = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\BLKOPFREWAT")  # 配置-有效相态
                CONV_METH_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\CONV_METH")  # 配置-收敛
                BASIS_RR_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\BASIS_RR")  # 配置-操作规范-回流比
                RR_BASIS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\RR_BASIS")  # 配置-操作规范-回流比
                BASIS_L1_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\BASIS_L1")  # 配置-操作规范-回流速率
                L1_BASIS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\L1_BASIS")  # 配置-操作规范-回流速率
                BASIS_D_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\BASIS_D")  # 配置-操作规范-馏出物流率
                D_BASIS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\D_BASIS")  # 配置-操作规范-馏出物流率
                BASIS_B_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\BASIS_B")  # 配置-操作规范-塔底物流率
                B_BASIS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\B_BASIS")  # 配置-操作规范-塔底物流率
                BASIS_VN_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\BASIS_VN")  # 配置-操作规范-再沸蒸汽流速
                VN_BASIS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\VN_BASIS")  # 配置-操作规范-再沸蒸汽流速
                BASIS_BR_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\BASIS_BR")  # 配置-操作规范-再沸比
                BR_BASIS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\BR_BASIS")  # 配置-操作规范-再沸比
                Q1_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\Q1")  # 配置-操作规范-冷凝器负荷
                QN_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\QN")  # 配置-操作规范-再沸器负荷
                DF_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\D:F")  # 配置-操作规范-馏出物进料比
                DF_BASIS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\D:F_BASIS")  # 配置-操作规范-馏出物进料比-单位
                BF_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\B:F")  # 配置-操作规范-馏出物进料比
                BF_BASIS_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\B:F_BASIS")  # 配置-操作规范-馏出物进料比-单位
                # RW_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\RW")  # 配置-自由水回流比
                self.add_if_not_empty(RadFrac_data["CONFIG_DATA"], CALC_MODE_NODE, "CALC_MODE")
                self.add_if_not_empty(RadFrac_data["CONFIG_DATA"], NSTAGE_NODE, "NSTAGE")
                self.add_if_not_empty(RadFrac_data["CONFIG_DATA"], CONDENSER_NODE, "CONDENSER")
                self.add_if_not_empty(RadFrac_data["CONFIG_DATA"], REBOILER_NODE, "REBOILER")
                self.add_if_not_empty(RadFrac_data["CONFIG_DATA"], NO_PHASE, "NO_PHASE")
                self.add_if_not_empty(RadFrac_data["CONFIG_DATA"], BLKOPFREWAT, "BLKOPFREWAT")
                self.add_if_not_empty(RadFrac_data["CONFIG_DATA"], CONV_METH_NODE, "CONV_METH")
                for i, OP_SPEC_DATA in enumerate(RadFrac_data["CONFIG_DATA"]["OP_SPEC"]):
                    self.add_if_not_empty(OP_SPEC_DATA, BASIS_RR_NODE, "BASIS_RR_VALUE", None, "BASIS_RR_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, RR_BASIS_NODE, "BASIS_RR_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, BASIS_L1_NODE, "BASIS_L1_VALUE", "BASIS_L1_UNITS","BASIS_L1_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, L1_BASIS_NODE, "BASIS_L1_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, BASIS_D_NODE, "BASIS_D_VALUE", "BASIS_D_UNITS", "BASIS_D_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, D_BASIS_NODE, "BASIS_D_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, BASIS_B_NODE, "BASIS_B_VALUE", "BASIS_B_UNITS", "BASIS_B_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, B_BASIS_NODE, "BASIS_B_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, BASIS_VN_NODE, "BASIS_VN_VALUE", "BASIS_VN_UNITS","BASIS_VN_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, VN_BASIS_NODE, "BASIS_VN_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, BASIS_BR_NODE, "BASIS_BR_VALUE", None, "BASIS_BR_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, DF_NODE, "DF_VALUE", None, "DF_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, DF_BASIS_NODE, "DF_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, BF_NODE, "BF_VALUE", None, "BF_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, BF_BASIS_NODE, "BF_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, BR_BASIS_NODE, "BASIS_BR_BASIS")
                    self.add_if_not_empty(OP_SPEC_DATA, Q1_NODE, "Q1_VALUE", "Q1_UNITS")
                    self.add_if_not_empty(OP_SPEC_DATA, QN_NODE, "QN_VALUE", "QN_UNITS")
                for i, FEED_DATA in enumerate(RadFrac_data["FEED_STAGE_DATA"]):
                    FEED_STAGE = FEED_DATA["FEED_STAGE"]
                    FEED_CONVEN_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\FEED_CONVEN\{FEED_STAGE}")  # 流股-进料流股-常规
                    FEED_STAGE_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\FEED_STAGE\{FEED_STAGE}")  # 流股-进料流股-塔板
                    FEED_CONVEN_NODES.Value = FEED_DATA["FEED_CONVEN"]
                    FEED_STAGE_NODES.Value = FEED_DATA["FEED_STAGE_VALUE"]
                for i, PROD_DATA in enumerate(RadFrac_data["PROD_STAGE_DATA"]):
                    PROD_STAGE = PROD_DATA["PROD_STAGE"]
                    PROD_PHASE_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PROD_PHASE\{PROD_STAGE}")  # 流股-产品流股-相态
                    PROD_STAGE_NODES = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PROD_STAGE\{PROD_STAGE}")  # 流股-产品流股-塔板
                    PROD_PHASE_NODES.Value = PROD_DATA["PROD_PHASE"]
                    PROD_STAGE_NODES.Value = PROD_DATA["PROD_STAGE_VALUE"]
                # 添加压力
                VIEW_PRES_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\VIEW_PRES")  # 压力-查看
                if RadFrac_data["PRES_DATA"]["VIEW_PRES"] == "TOP/BOTTOM": # 压力-查看-塔顶/塔底
                    VIEW_PRES_NODE.Value = "TOP/BOTTOM"
                    PRES1_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PRES1")  # 压力-查看-塔板1压力
                    OPT_PRES_TOP_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\OPT_PRES_TOP")  # 压力-查看-塔板2压力-选项
                    PRES2_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\PRES2")  # 压力-查看-塔板2压力
                    DP_COND_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DP_COND")  # 压力-查看-塔板2压力-冷凝器压降
                    OPT_PRES_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\OPT_PRES")  # 压力-查看-塔其余部分压降
                    DP_STAGE_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DP_STAGE")  # 压力-查看-塔其余部分压降-塔板压降
                    DP_COL_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\DP_COL")
                    for i, STAGE_PRES_DATA in enumerate(RadFrac_data["PRES_DATA"]["STAGE_PRES"]):  # 压力-查看-塔其余部分压降-塔压降
                        self.add_if_not_empty(STAGE_PRES_DATA, PRES1_NODE, "PRES1_VALUE", "PRES1_UNITS")
                        self.add_if_not_empty(STAGE_PRES_DATA, OPT_PRES_TOP_NODE, "OPT_PRES_TOP")
                        self.add_if_not_empty(STAGE_PRES_DATA, PRES2_NODE, "PRES2_VALUE", "PRES2_UNITS")
                        self.add_if_not_empty(STAGE_PRES_DATA, DP_COND_NODE, "DP_COND_VALUE", "DP_COND_UNITS")
                        self.add_if_not_empty(STAGE_PRES_DATA, OPT_PRES_NODE, "OPT_PRES")
                        self.add_if_not_empty(STAGE_PRES_DATA, DP_STAGE_NODE, "DP_STAGE_VALUE", "DP_STAGE_UNITS")
                        self.add_if_not_empty(STAGE_PRES_DATA, DP_COL_NODE, "DP_COL_VALUE", "DP_COL_UNITS")
                if RadFrac_data["PRES_DATA"]["VIEW_PRES"] == "PROFILE":  # 压力-查看-压力分布
                    VIEW_PRES_NODE.Value = "PROFILE"
                    for i, STAGE_PRES_DATA in enumerate(RadFrac_data["PRES_DATA"]["STAGE_PRES"]):
                        PRES_STAGE = STAGE_PRES_DATA["PRES_STAGE"]
                        STAGE_PRES_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\STAGE_PRES")
                        STAGE_PRES_NODE.Elements.InsertRow(0, 0)
                        STAGE_PRES_NODE.Elements.LabelNode(0, 0)[0].Value = PRES_STAGE
                        self.add_if_not_empty(STAGE_PRES_DATA, STAGE_PRES_NODE.Elements(0), "PRES_VALUE", "PRES_UNITS")
                    # if view_pres == "PDROP":  # 压力-查看-塔段压降  暂未实现
                # 添加冷凝器
                if "CONDENSER_DATA" in RadFrac_data:
                    OPT_COND_SPC_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\OPT_COND_SPC")  # 冷凝器-冷凝器规范
                    T1_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\T1")  # 冷凝器-冷凝器规范-温度
                    BASIS_RDV_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\BASIS_RDV")  # 冷凝器-冷凝器规范-馏出物汽相分率
                    SC_TEMP_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\SC_TEMP")  # 冷凝器-冷凝器规范-过冷规范-过冷温度
                    SC_OPTION_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Input\SC_OPTION")  # 冷凝器-冷凝器规范
                    self.add_if_not_empty(RadFrac_data['CONDENSER_DATA'], OPT_COND_SPC_NODE, "OPT_COND_SPC")
                    self.add_if_not_empty(RadFrac_data['CONDENSER_DATA'], T1_NODE, "T1_VALUE", "T1_UNITS")
                    self.add_if_not_empty(RadFrac_data['CONDENSER_DATA'], BASIS_RDV_NODE, "BASIS_RDV_VALUE", None, "BASIS_RDV_BASIS")
                    self.add_if_not_empty(RadFrac_data['CONDENSER_DATA'], SC_TEMP_NODE, "SC_TEMP_VALUE", "SC_TEMP_UNITS")
                    self.add_if_not_empty(RadFrac_data['CONDENSER_DATA'], SC_OPTION_NODE, "SC_OPTION")
                # 添加设计规定
                if "DESIGN_SPEC_DATA" in RadFrac_data:
                    DESIGN_SPEC_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Subobjects\Design Specs")
                    base_node = fr"\Data\Blocks\{block}\Subobjects\Design Specs"
                    for design_spec_data in RadFrac_data["DESIGN_SPEC_DATA"]:
                        design_spec_id = design_spec_data["SPEC_ID"]
                        DESIGN_SPEC_NODE.Elements.Add(design_spec_id)
                        VALUE_NODE = self.aspen.Tree.FindNode(fr"{base_node}\{design_spec_id}\Input\VALUE\{design_spec_id}")
                        SPEC_TYPE_NODE = self.aspen.Tree.FindNode(fr"{base_node}\{design_spec_id}\Input\SPEC_TYPE\{design_spec_id}")
                        OPT_SPC_STR_NODE = self.aspen.Tree.FindNode(fr"{base_node}\{design_spec_id}\Input\OPT_SPC_STR\{design_spec_id}")
                        self.add_if_not_empty(design_spec_data, VALUE_NODE, "SPEC_VALUE")
                        self.add_if_not_empty(design_spec_data, SPEC_TYPE_NODE, "SPEC_TYPE_VALUE")
                        self.add_if_not_empty(design_spec_data, OPT_SPC_STR_NODE, "OPT_SPC_STR_VALUE")
                        COMPS_NODE = self.aspen.Tree.FindNode(fr"{base_node}\{design_spec_id}\Input\SPEC_COMPS\{design_spec_id}")
                        for i, comp in enumerate(design_spec_data["COMP_DATA"]):
                            COMPS_NODE.Elements.InsertRow(0, 0)
                            COMPS_NODE.Elements(0, 0).Value = comp
                        SPEC_STREAMS_NODE = self.aspen.Tree.FindNode(fr"{base_node}\{design_spec_id}\Input\SPEC_STREAMS\{design_spec_id}")
                        for i, spec_stream in enumerate(design_spec_data["SPEC_STREAMS"]):
                            SPEC_STREAMS_NODE.Elements.InsertRow(0, 0)
                            SPEC_STREAMS_NODE.Elements(0, 0).Value = spec_stream
                # 添加设计变化
                if "VARY_DATA" in RadFrac_data:
                    VARY_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block}\Subobjects\Vary")
                    base_node = fr"\Data\Blocks\{block}\Subobjects\Vary"
                    for vary_data in RadFrac_data["VARY_DATA"]:
                        vary_id = vary_data["VARY_ID"]
                        VARY_NODE.Elements.Add(vary_id)
                        VALUE_NODE = self.aspen.Tree.FindNode(fr"{base_node}\{vary_id}\Input\VALUE\{vary_id}")
                        VARTYPE_NODE = self.aspen.Tree.FindNode(fr"{base_node}\{vary_id}\Input\VARTYPE\{vary_id}")
                        LB_NODE = self.aspen.Tree.FindNode(fr"{base_node}\{vary_id}\Input\LB\{vary_id}")
                        UB_NODE = self.aspen.Tree.FindNode(fr"{base_node}\{vary_id}\Input\UB\{vary_id}")
                        STEP_NODE = self.aspen.Tree.FindNode(fr"{base_node}\{vary_id}\Input\STEP\{vary_id}")
                        self.add_if_not_empty(vary_data, VALUE_NODE, "VARY_VALUE")
                        self.add_if_not_empty(vary_data, VARTYPE_NODE, "VARTYPE_VALUE")
                        self.add_if_not_empty(vary_data, LB_NODE, "LB_VALUE")
                        self.add_if_not_empty(vary_data, UB_NODE, "UB_VALUE")
                        self.add_if_not_empty(vary_data, STEP_NODE, "STEP_VALUE")
                        if vary_data["COMP_DATA"] !=[]:
                            COMPS_NODE = self.aspen.Tree.FindNode(fr"{base_node}\{vary_id}\Input\VARY_COMPS\{vary_id}")
                            for i, comp in enumerate(vary_data["COMP_DATA"]):
                                COMPS_NODE.Elements.InsertRow(0, 0)
                                COMPS_NODE.Elements(0, 0).Value = comp
            print(f"成功添加blocks_RadFrac_data")
        except Exception as e:
            print(f"在添加blocks_RadFrac_data时出错: {e}")
            raise


    def run_simulation(self):
        """运行模拟并保存结果到CSV文件"""
        # 运行模拟
        try:
            print("开始运行模拟...")
            self.aspen.Engine.Run2()
            print("模拟运行完成")
        except Exception as e:
            print(f"模拟运行失败: {e}")


    def check_convergence(self):
        """检查模拟是否收敛"""
        try:
            # 收敛节点待调测
            # Conv_node = self.aspen.Tree.FindNode(fr"\Data\Results Summary\Conv-Sum\TEAR-SUMMARY\Output") #收敛结果节点
            # CVSTAT_node = self.aspen.Tree.FindNode(fr"\Data\Results Summary\Conv-Sum\TEAR-SUMMARY\Output\Output\CVSTAT") #结果-收敛状态
            # BLK_node = self.aspen.Tree.FindNode("\Data\Results Summary\Run-Status\Output\BLKSTAT")
            # convstat_node = self.aspen.Tree.FindNode("\Data\Convergence\Convergence\$OLVER01\Output\BLKSTAT") #收敛-收敛状态
            # self.aspen.Tree.FindNode("\Data\Convergence\Convergence\$OLVER01\Output\ERR_TOL2\30")
            # self.aspen.Tree.FindNode("\Data\Convergence\Conv-Options\Input\WEG_MAXIT")
            # self.aspen.Tree.FindNode("\Data\Convergence\Conv-Options\Input\WEG_QMIN")
            # self.aspen.Tree.FindNode("\Data\Convergence\Conv-Options\Input\WEG_QMAX")
            # self.aspen.Tree.FindNode("\Data\Convergence\Conv-Options\Input\TEAR_METHOD")
            # 获取收敛状态
            conv_status_node = self.aspen.Tree.FindNode(r"\Data\Results Summary\Conv-Sum\Output\STREAMID\1")
            conv_status = conv_status_node.Value

            if conv_status == "RECYCLE":
                print("模拟已收敛")
                return True
            else:
                print(f"模拟未收敛，状态: {conv_status}")
                return False

        except Exception as e:
            print(f"检查收敛状态时出错: {e}")
            return False

    def get_all_simulation_results(self, config: Dict[str, Any]):
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = fr"D:\aspen\resultfile\aspen_result_export_{timestamp}.xlsx"

        # 创建一个Excel写入器
        with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
            # 1. 首先处理流结果，保存到"Stream Summary"工作表
            table_node = self.aspen.Tree.FindNode(fr"\Data\Results Summary\Stream-Sum\Stream-Sum\Table")

            row_count = table_node.Elements.RowCount(0)
            col_count = table_node.Elements.RowCount(1)

            # 获取列名称
            col_names = []
            for j in range(col_count):
                try:
                    col_name = table_node.Elements.LabelNode(1, j)[0].Value
                    col_names.append(col_name)
                except:
                    col_names.append(f"Col_{j + 1}")

            # 准备数据
            rows_list = []
            row_names = []

            for i in range(row_count):
                try:
                    # 获取行名称
                    row_name = table_node.Elements.LabelNode(0, i)[0].Value
                    row_names.append(row_name)

                    # 获取行数据
                    row_data = {}
                    for j in range(col_count):
                        try:
                            cell_value = table_node.Elements(i, j).Value
                            row_data[col_names[j]] = cell_value if cell_value is not None else "N/A"
                        except:
                            row_data[col_names[j]] = "N/A"

                    rows_list.append(row_data)
                except Exception as e:
                    print(f"处理第 {i + 1} 行时出错: {e}")

            # 创建DataFrame并保存到工作表
            if rows_list:
                df_stream = pd.DataFrame(rows_list, index=row_names)
                df_stream.to_excel(writer, sheet_name='Stream Summary')

            # 2. 处理每个block的结果，为每个block创建单独的工作表
            for i, block in enumerate(config.get('blocks', [])):
                block_name = block['name']
                if block['type'] == "DSTWU":
                    # 收集DSTWU block的所有结果
                    block_results = {}
                    # 最小回流比
                    min_reflux = self.safe_get_node_value(fr"\Data\Blocks\{block_name}\Output\MIN_REFLUX")
                    block_results['MIN_REFLUX'] = min_reflux
                    # 实际回流比
                    act_reflux = self.safe_get_node_value(fr"\Data\Blocks\{block_name}\Output\ACT_REFLUX")
                    block_results['ACT_REFLUX'] = act_reflux
                    # 最小塔板数
                    min_stages = self.safe_get_node_value(fr"\Data\Blocks\{block_name}\Output\MIN_STAGES")
                    block_results['MIN_STAGES'] = min_stages
                    # 实际塔板数
                    act_stages = self.safe_get_node_value(fr"\Data\Blocks\{block_name}\Output\ACT_STAGES")
                    block_results['ACT_STAGES'] = act_stages
                    # 进料塔板
                    feed_locatn = self.safe_get_node_value(fr"\Data\Blocks\{block_name}\Output\FEED_LOCATN")
                    block_results['FEED_LOCATN'] = feed_locatn
                    # 进料上方实际塔板数
                    rect_stages = self.safe_get_node_value(fr"\Data\Blocks\{block_name}\Output\RECT_STAGES")
                    block_results['RECT_STAGES'] = rect_stages
                    # 冷凝器热负荷
                    cond_duty = self.safe_get_node_value(fr"\Data\Blocks\{block_name}\Output\COND_DUTY")
                    block_results['COND_DUTY'] = cond_duty
                    # 冷凝器热负荷单位
                    cond_duty_units = self.safe_get_node_units(fr"\Data\Blocks\{block_name}\Output\COND_DUTY")
                    block_results['COND_DUTY_UNITS'] = cond_duty_units
                    # 再沸器热负荷
                    reb_duty = self.safe_get_node_value(fr"\Data\Blocks\{block_name}\Output\REB_DUTY")
                    block_results['REB_DUTY'] = reb_duty
                    # 再沸器热负荷单位
                    reb_duty_units = self.safe_get_node_units(fr"\Data\Blocks\{block_name}\Output\REB_DUTY")
                    block_results['REB_DUTY_UNITS'] = reb_duty_units
                    # 馏出物温度
                    distil_temp = self.safe_get_node_value(fr"\Data\Blocks\{block_name}\Output\DISTIL_TEMP")
                    block_results['DISTIL_TEMP'] = distil_temp
                    # 馏出物温度单位
                    distil_temp_units = self.safe_get_node_units(fr"\Data\Blocks\{block_name}\Output\DISTIL_TEMP")
                    block_results['DISTIL_TEMP_UNITS'] = distil_temp_units
                    # 塔底物温度
                    bottom_temp = self.safe_get_node_value(fr"\Data\Blocks\{block_name}\Output\BOTTOM_TEMP")
                    block_results['BOTTOM_TEMP'] = bottom_temp
                    # 塔底物温度单位
                    bottom_temp_units = self.safe_get_node_units(fr"\Data\Blocks\{block_name}\Output\BOTTOM_TEMP")
                    block_results['BOTTOM_TEMP_UNITS'] = bottom_temp_units
                    # 馏出物进料比率
                    dist_vs_feed = self.safe_get_node_value(fr"\Data\Blocks\{block_name}\Output\DIST_VS_FED")
                    block_results['DIST_VS_FEED'] = dist_vs_feed

                    # 将block结果转换为DataFrame
                    # 转换为列格式：参数名称作为一列，值作为另一列
                    df_block = pd.DataFrame(list(block_results.items()), columns=['Parameter', 'Value'])

                    # 保存到以block名称命名的工作表
                    # 确保工作表名称有效（Excel工作表名称有长度和字符限制）
                    sheet_name = block_name + "_result"
                    df_block.to_excel(writer, sheet_name=sheet_name, index=False)

                    print(f"Block '{block_name}' 的结果已保存到工作表 '{sheet_name}'")

                # 可以添加其他block类型的处理
                # elif block['type'] == "RADFRAC":
                #     # 处理RADFRAC类型的block
                #     pass

        print(f"所有数据已保存到Excel文件: {os.path.abspath(excel_filename)}")
        result_path = os.path.abspath(excel_filename)
        return result_path

    def save_simulation(self, file_path: str):
        """
        保存模拟文件

        Args:
            file_path: 保存路径
        """
        try:
            self.aspen.SaveAs(file_path)
            print(f"模拟文件已保存到: {file_path}")
        except Exception as e:
            print(f"保存模拟文件失败: {e}")
            raise

    def close_simulation(self):
        """关闭模拟"""
        try:
            self.aspen.Close()
            print("模拟已关闭")
            pythoncom.CoUninitialize()
        except Exception as e:
            print(f"关闭模拟时出错: {e}")
            raise

def analyze_aspen_error(error_detail):
    """
    分析Aspen模拟配置写入错误返回的错误信息，判断错误类型
    """
    # 定义错误类型映射字典列表
    error_type_mappings = [
        {
            "keyword": "write_components_to_aspen",
            "error_message": "components配置写入错误"
        },
        {
            "keyword": "write_property_methods_to_aspen",
            "error_message": "property_methods配置写入错误"
        },
        {
            "keyword": "write_blocks_to_aspen",
            "error_message": "blocks配置写入错误"
        },
        {
            "keyword": "write_stream_to_aspen",
            "error_message": "stream配置写入错误"
        },
        {
            "keyword": "write_block_connections_to_aspen",
            "error_message": "block_connections配置写入错误"
        },
        {
            "keyword": "write_stream_data_to_aspen",
            "error_message": "stream_data配置写入错误"
        },
        {
            "keyword": "write_reactions_data_to_aspen",
            "error_message": "reactions_data配置写入错误"
        },
        {
            "keyword": "write_blocks_Mixer_data_to_aspen",
            "error_message": "blocks_Mixer_data配置写入错误"
        },
        {
            "keyword": "write_blocks_Valve_data_to_aspen",
            "error_message": "blocks_Valve_data配置写入错误"
        },
        {
            "keyword": "write_blocks_Compr_data_to_aspen",
            "error_message": "blocks_Compr_data配置写入错误"
        },
        {
            "keyword": "write_blocks_Heater_data_to_aspen",
            "error_message": "blocks_Heater_data配置写入错误"
        },
        {
            "keyword": "write_blocks_Pump_data_to_aspen",
            "error_message": "blocks_Pump_data配置写入错误"
        },
        {
            "keyword": "write_blocks_RStoic_data_to_aspen",
            "error_message": "blocks_RStoic_data配置写入错误"
        },
        {
            "keyword": "write_blocks_RPlug_data_to_aspen",
            "error_message": "blocks_RPlug_data配置写入错误"
        },
        {
            "keyword": "write_blocks_Flash2_data_to_aspen",
            "error_message": "blocks_Flash2_data配置写入错误"
        },
        {
            "keyword": "write_blocks_Sep_data_to_aspen",
            "error_message": "blocks_Sep_data配置写入错误"
        },
        {
            "keyword": "write_blocks_Sep2_data_to_aspen",
            "error_message": "blocks_Sep2_data配置写入错误"
        },
        {
            "keyword": "write_blocks_RadFrac_data_to_aspen",
            "error_message": "blocks_RadFrac_data配置写入错误"
        }
    ]
    for error_map in error_type_mappings:
        if error_map["keyword"] in error_detail:
            return error_map["error_message"]

    # 如果没有匹配到已知错误类型
    return "未知配置写入错误"
class AspenEvents:
    def __init__(self):
        self.messages = []  # 存储所有控制面板消息
        self.current_session_messages = []  # 存储本次会话的消息
    def OnControlPanelMessage(self, clear, msg):
        if clear:
            print("控制面板已清空")
        else:
            print(f"控制面板消息: {msg}")
            # 存储消息
            self.messages.append(msg)
            self.current_session_messages.append(msg)
            # 可以在这里添加自定义处理逻辑
            self.process_control_panel_message(msg)

    def OnDialogSuppressed(self, msg, result):
        print(f"对话框被抑制: {msg}, 默认结果: {result}")

    def OnGUIClosing(self):
        print("ASPEN GUI正在关闭")
    def process_control_panel_message(self, message):
        """处理控制面板消息的自定义逻辑"""
        # 例如：记录到文件
        try:
            os.makedirs("../aspenlog", exist_ok=True)
            message_file = f"../aspenlog/aspen_control_panel.log"
            with open(message_file, "a", encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()}: {message}\n")
        except Exception as e:
            print(f"写入日志文件失败: {e}")

    def get_current_session_messages(self):
        """获取本次会话的所有控制面板消息"""
        return self.current_session_messages

    def get_current_session_messages_as_string(self):
        """获取本次会话的所有控制面板消息，作为字符串"""
        return "\n".join(self.current_session_messages)

    def get_all_messages(self):
        """获取所有控制面板消息"""
        return self.messages


@app.route('/run-aspen-simulation', methods=['POST'])
def run_aspen_simulation():
    # 获取请求数据
    config = request.json
    if not config:
        return jsonify({"error": "请求体为空"}), 400

    try:
    # 尝试写入配置到ASPEN模拟文件
        # 初始化模拟管理器
        aspen_manager = AspenSimulationManager()

        # 创建新模拟
        aspen_manager.create_new_simulation(fr"D:\aspen\orgfile\test.bkp")

        # 创建唯一的结果输出文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file_path = fr"D:\aspen\bkpfile\output_{timestamp}.bkp"

        # 加载JSON配置
        loaded_config = aspen_manager.load_json_config(config)

        # 将配置写入Aspen
        aspen_manager.write_config_to_aspen(loaded_config)

    except Exception as e:
        # 获取详细的错误信息，包括具体是哪一步配置写入失败
        error_detail = f"配置写入失败: {str(e)}\n错误位置: {traceback.format_exc()}"
        print(f"n错误位置: {traceback.format_exc()}")
        error_message = analyze_aspen_error(error_detail)
        # 保存模拟文件
        aspen_manager.save_simulation(output_file_path)
        return jsonify({
            "success": False,
            "aspen_file_path": output_file_path,
            "error_type": "模拟配置写入失败",
            "error_message": f"{error_message}: {str(e)}"
        }), 201

    try:
        # 运行模拟文件
        aspen_manager.run_simulation()

        # 获取ASPEN控制面板消息
        current_messages_str = aspen_manager.get_control_panel_messages()

        # 保存模拟文件
        aspen_manager.save_simulation(output_file_path)

        if "No Errors" in current_messages_str:
            try:
                # 获取模拟文件运行结果
                result_absolute_path = aspen_manager.get_all_simulation_results(loaded_config)
            except Exception as e:
                print(f"保存结果文件错误: {str(e)}")
            # 返回生成的文件路径
            return jsonify({
                "success": True,
                "aspen_file_path": output_file_path,
                "result_file_path": result_absolute_path,
                "message": "Aspen模拟已成功运行并保存"
            })
        elif "**  ERROR" or "*** SEVERE ERROR" in current_messages_str:
            return jsonify({
                "success": False,
                "aspen_file_path": output_file_path,
                "error_type": "模拟运行过程发生错误",
                "error_message": current_messages_str
            }), 201
    except Exception as e:
        # 获取ASPEN控制面板消息
        current_messages_str = aspen_manager.get_control_panel_messages()
        return jsonify({
            "success": False,
            "error_message": f"{str(e)}:{current_messages_str}",
            "error_type": "模拟运行过程失败"
        }), 201
    finally:
        # 确保关闭模拟
        if aspen_manager:
            try:
                aspen_manager.close_simulation()
            except:
                pass

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "aspen_available": True
    }

if __name__ == "__main__":
    # 启动HTTP服务，默认端口6000
    print(f"启动Aspen模拟服务")
    app.run(host="127.0.0.1", port=os.getenv("ASPEN_SIMULATOR_PORT"), debug=True, use_reloader=False)
