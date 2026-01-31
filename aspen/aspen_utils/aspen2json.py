import win32com.client
import pythoncom
import json
import os
from typing import Dict, List, Any, Optional

class AspenToJSONConverter:
    def __init__(self, aspen_file_path):
        """初始化 Aspen Plus 连接"""
        self.aspen = None
        self.aspen_file_path = aspen_file_path
        self.data = {}

    def connect_to_aspen(self):
        """连接到 Aspen Plus 实例"""
        try:
            self.aspen = win32com.client.Dispatch("Apwn.Document")
            if os.path.exists(self.aspen_file_path):
                self.aspen.InitFromArchive2(os.path.abspath(self.aspen_file_path))
                print(f"成功加载 Aspen Plus 文件: {self.aspen_file_path}")
                return True
            else:
                print("文件不存在")
                return False
        except Exception as e:
            print(f"连接 Aspen Plus 失败: {e}")
            return False

    def disconnect(self):
        """断开与 Aspen Plus 的连接"""
        if self.aspen:
            self.aspen.Close()
            pythoncom.CoUninitialize()
            print("已断开与 Aspen Plus 的连接")

    def safe_get_node_value(self, node_path: str, default: Any = None) -> Any:
        """安全获取节点值，避免节点不存在时抛出异常"""
        try:
            node = self.aspen.Tree.FindNode(node_path)
            if node:
                return node.Value
            else:
                return default
        except Exception as e:
            print(f"获取节点 {node_path} 值时出错: {e}")
            return default

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

    def extract_metadata(self):
        """提取元数据"""
        try:
            description = self.safe_get_node_value(r"\Data\Results Summary\Run-Status\Output\DESCRIPTION", "Unknown")

            self.data["metadata"] = {
                "description": description
            }
            print("元数据提取完成")
        except Exception as e:
            print(f"提取元数据时出错: {e}")
            self.data["metadata"] = {"description": "Unknown"}

    def extract_setup(self):
        """提取设置数据"""
        try:
            setup_data = {}
            setup_data["sim_options"] = {}
            # 1. 提取设置-计算选项配置
            ENERGY_BAL_VALUE = self.safe_get_node_value(f"\Data\Setup\Sim-Options\Input\ENERGY_BAL") #设置-计算选项-执行热量平衡计算
            self.add_if_not_empty(setup_data["sim_options"], "energy_bal_value", ENERGY_BAL_VALUE)
            self.data["setup"] = setup_data
            print(f"设置数据提取完成")
        except Exception as e:
            print(f"提取设置数据时出错: {e}")

    def extract_components(self):
        """提取组分数据"""
        try:
            components = []

            # 1. 首先从 CID 目录获取所有子节点的值
            cid_nodes = self.get_child_nodes(r"\Data\Components\Comp-Lists\GLOBAL\Input\CID")
            cid_values = []

            for cid_node in cid_nodes:
                cid_value = self.safe_get_node_value(fr"\Data\Components\Comp-Lists\GLOBAL\Input\CID\{cid_node}")
                cid_values.append(cid_value)

            print(f"从 CID 目录获取到 {len(cid_values)} 个组分 ID")

            # 2. 使用 CID 值作为索引，从其他目录获取对应的值
            for i, cid in enumerate(cid_values, 1):
                # 获取组分名称
                name = self.safe_get_node_value(fr"\Data\Components\Specifications\Input\ANAME\{cid}", f"Component_{i}")

                # 获取 CAS 号
                casn = self.safe_get_node_value(fr"\Data\Components\Specifications\Input\CASN\{cid}", "")

                # 获取数据库名称
                dbname = self.safe_get_node_value(fr"\Data\Components\Specifications\Input\DBNAME\{cid}", "")

                # 数据库不存在的自定义组分不抽取
                if dbname is not None:
                    components.append({
                        "cid": cid,
                        "name": name,
                        "cas_number": casn,
                        "database_name": dbname
                    })
            self.data["components"] = components
            print(f"组分数据提取完成，共 {len(components)} 个组分")
        except Exception as e:
            print(f"提取组分数据时出错: {e}")
            self.data["components"] = []

    def extract_property_methods(self):
        """提取物性方法"""
        try:
            property_methods = []
            # 获取所有物性方法
            prop_methods_node = self.aspen.Tree.FindNode(r"\Data\Properties\Property Methods")
            # 获取基准方法
            basis_method = self.safe_get_node_value(
                fr"\Data\Properties\Specifications\Input\GBASEOPSET", "")

            if prop_methods_node and prop_methods_node.Elements.Count > 0:
                for method in prop_methods_node.Elements:
                    method_name = method.Name
                    if basis_method == method_name:
                        property_methods.append({
                            "method_name": method_name,
                            "is_basis_method": True
                        })
                    else:
                        property_methods.append({
                            "method_name": method_name,
                            "is_basis_method": False
                        })
            self.data["property_methods"] = property_methods
            print(f"物性方法提取完成，共 {len(property_methods)} 个方法")

        except Exception as e:
            print(f"提取物性方法时出错: {e}")
            self.data["property_methods"] = {}

    def extract_henry_components(self):
        """提取Henry组分"""
        try:
            henry_components = {}

            # 获取Henry组分集的子目录
            henry_sets = self.get_child_nodes(r"\Data\Components\Henry-Comps")

            for henry_set in henry_sets:
                # 获取当前Henry组分集的CID节点
                cid_nodes = self.get_child_nodes(fr"\Data\Components\Henry-Comps\{henry_set}\Input\CID")

                components_in_set = []
                for cid_node in cid_nodes:
                    # 获取CID节点的值（化学式）
                    formula = self.safe_get_node_value(
                        fr"\Data\Components\Henry-Comps\{henry_set}\Input\CID\{cid_node}")

                    if formula:
                        components_in_set.append({
                            "node": cid_node,
                            "formula": formula
                        })

                henry_components[henry_set] = {
                    "components": components_in_set
                }

            self.data["henry_components"] = henry_components
            print(f"Henry组分提取完成，共 {len(henry_components)} 个Henry组分集")

        except Exception as e:
            print(f"提取Henry组分时出错: {e}")
            self.data["henry_components"] = {}

    # def extract_custom_component_parameters(self):
    #     """提取自定义组分参数"""
    #     try:
    #         custom_params = {}
    #
    #         # 检查USRDEF目录是否存在
    #         usrdef_path = r"\Data\Properties\Parameters\Pure Components\USRDEF"
    #         usrdef_node = self.aspen.Tree.FindNode(usrdef_path)
    #
    #         if not usrdef_node:
    #             print("USRDEF目录不存在，跳过自定义组分参数提取")
    #             self.data["custom_component_parameters"] = {}
    #             return
    #
    #         # 获取SETNO目录下的参数和单位
    #         setno_nodes = self.get_child_nodes(fr"{usrdef_path}\Input\SETNO")
    #
    #         setno_params = {}
    #         for node in setno_nodes:
    #             value = self.safe_get_node_value(
    #                 fr"{usrdef_path}\Input\SETNO\{node}")
    #             units = self.safe_get_node_units(
    #                 fr"{usrdef_path}\Input\SETNO\{node}")
    #
    #             setno_params[node] = {
    #                 "value": value,
    #                 "units": units
    #             }
    #
    #         # 获取VALUE目录下的组分名称和值
    #         value_nodes = self.get_child_nodes(fr"{usrdef_path}\Input\UVALUE")
    #
    #         component_values = {}
    #         for node in value_nodes:
    #             value = self.safe_get_node_value(
    #                 fr"{usrdef_path}\Input\UVALUE\{node}")
    #
    #             component_values[node] = value
    #
    #         custom_params = {
    #             "setno_parameters": setno_params,
    #             "component_values": component_values
    #         }
    #
    #         self.data["custom_component_parameters"] = custom_params
    #         print(f"自定义组分参数提取完成，SETNO参数: {len(setno_params)} 个, 组分值: {len(component_values)} 个")
    #
    #     except Exception as e:
    #         print(f"提取自定义组分参数时出错: {e}")
    #         self.data["custom_component_parameters"] = {}

    def get_block_type(self, node_path, HAP_RECORDTYPE):
        node = self.aspen.Tree.FindNode(node_path)
        return node.AttributeValue(HAP_RECORDTYPE)
    def extract_blocks(self):
        """提取单元操作及其类型"""
        try:
            blocks_node = self.aspen.Tree.FindNode(r"\Data\Blocks")
            if not blocks_node:
                print("未找到Blocks节点")
                self.data["blocks"] = []
                return

            blocks = []
            for block_name in self.get_child_nodes(r"\Data\Blocks"):
                # 获取单元操作类型
                block_node = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block_name}")
                block_type = block_node.AttributeValue(6)

                blocks.append({
                    "name": block_name,
                    "type": block_type
                })

            self.data["blocks"] = blocks
            print(f"单元操作提取完成，共 {len(blocks)} 个单元操作")

        except Exception as e:
            print(f"提取单元操作时出错: {e}")
            self.data["blocks"] = []

    def extract_streams(self):
        """提取物流"""
        try:
            streams = self.get_child_nodes(r"\Data\Streams")
            self.data["streams"] = streams
            print(f"物流提取完成，共 {len(streams)} 个物流")
        except Exception as e:
            print(f"提取物流时出错: {e}")
            self.data["streams"] = []

    def extract_stream_connections(self):
        """提取物流连接"""
        try:
            connections = {}
            streams = self.data.get("streams", [])

            for stream in streams:
                try:
                    conn_path = fr"\Data\Streams\{stream}\Connections"
                    conn_nodes = self.get_child_nodes(conn_path)

                    if conn_nodes:
                        connections[stream] = {}
                        for conn_node in conn_nodes:
                            node_path = fr"{conn_path}\{conn_node}"
                            value = self.safe_get_node_value(node_path)
                            connections[stream][conn_node] = value
                except Exception as e:
                    print(f"提取物流 {stream} 连接时出错: {e}")
                    continue

            self.data["stream_connections"] = connections
            print("物流连接提取完成")
        except Exception as e:
            print(f"提取物流连接时出错: {e}")
            self.data["stream_connections"] = {}

    def extract_block_connections(self):
        """提取物流连接"""
        try:
            connections = {}
            blocks = self.data.get("blocks", [])
            for block in blocks:
                try:
                    conn_path = fr"\Data\Blocks\{block['name']}\Connections"
                    conn_nodes = self.get_child_nodes(conn_path)
                    if conn_nodes:
                        connections[block['name']] = {}
                        for conn_node in conn_nodes:
                            node_path = fr"{conn_path}\{conn_node}"
                            value = self.safe_get_node_value(node_path)
                            connections[block['name']][conn_node] = value
                except Exception as e:
                    print(f"提取设备 {block['name']} 连接时出错: {e}")
                    continue

            self.data["block_connections"] = connections
            print("设备连接提取完成")
        except Exception as e:
            print(f"提取设备连接时出错: {e}")
            self.data["block_connections"] = {}

    def extract_streams_data(self):
        """提取Streams流股数据"""
        try:
            stream_data = {}
            Streams = self.data.get("streams", [])
            for stream in Streams:
                stream_data[stream] = {}
                MIXED_SPEC = self.safe_get_node_value(fr"\Data\Streams\{stream}\Input\MIXED_SPEC\MIXED")
                stream_data[stream]["MIXED_SPEC"] = MIXED_SPEC
                PRES_VALUE = self.safe_get_node_value(fr"\Data\Streams\{stream}\Input\PRES\MIXED")
                PRES_UNITS = self.safe_get_node_units(fr"\Data\Streams\{stream}\Input\PRES\MIXED")
                TEMP_VALUE = self.safe_get_node_value(fr"\Data\Streams\{stream}\Input\TEMP\MIXED")
                TEMP_UNITS = self.safe_get_node_units(fr"\Data\Streams\{stream}\Input\TEMP\MIXED")
                VFRAC_VALUE = self.safe_get_node_value(fr"\Data\Streams\{stream}\Input\VFRAC\MIXED")
                if MIXED_SPEC == "TP":
                    stream_data[stream]["pressure"] = {
                        "PRES_VALUE": PRES_VALUE,
                        "PRES_UNITS": PRES_UNITS
                    }
                    stream_data[stream]["temperature"] = {
                        "TEMP_VALUE": TEMP_VALUE,
                        "TEMP_UNITS": TEMP_UNITS
                    }
                elif MIXED_SPEC == "TV":
                    stream_data[stream]["temperature"] = {
                        "TEMP_VALUE": TEMP_VALUE,
                        "TEMP_UNITS": TEMP_UNITS
                    }
                    stream_data[stream]["vfrac"] = {
                        "VFRAC_VALUE": VFRAC_VALUE
                    }
                elif MIXED_SPEC == "PV":
                    stream_data[stream]["pressure"] = {
                        "PRES_VALUE": PRES_VALUE,
                        "PRES_UNITS": PRES_UNITS
                    }
                    stream_data[stream]["vfrac"] = {
                        "VFRAC_VALUE": VFRAC_VALUE
                    }
                # 提取流量数据
                FLOWBASE = self.safe_get_node_value(fr"\Data\Streams\{stream}\Input\FLOWBASE")  # 规定-总流量-基准
                TOTFLOW_VALUE = self.safe_get_node_value(fr"\Data\Streams\{stream}\Input\TOTFLOW") # 规定-总流量-值
                TOTFLOW_UNIT = self.safe_get_node_units(fr"\Data\Streams\{stream}\Input\TOTFLOW") # 规定-总流量-单位
                BASIS = self.safe_get_node_value(fr"\Data\Streams\{stream}\Input\BASIS")  # 规定-组成-基准
                flow_nodes = self.get_child_nodes(fr"\Data\Streams\{stream}\Input\FLOW\MIXED")   # 规定-组成
                flow_values = {}
                self.add_if_not_empty(flow_values, "FLOWBASE", FLOWBASE)
                self.add_if_not_empty(flow_values, "TOTFLOW_VALUE", TOTFLOW_VALUE, "TOTFLOW_UNITS", TOTFLOW_UNIT)
                self.add_if_not_empty(flow_values, "BASIS", BASIS)
                # 提取所有组分的name
                components = self.data.get("components", [])
                component_cids = [comp['cid'] for comp in components]
                for node in flow_nodes:
                    if node in component_cids: # 只提取components中的组分，自定义组分的配置不要提取
                        FLOW_VALUE = self.safe_get_node_value(fr"\Data\Streams\{stream}\Input\FLOW\MIXED\{node}")
                        FLOW_UNITS = self.safe_get_node_units(fr"\Data\Streams\{stream}\Input\FLOW\MIXED")
                #        FLOW_UNITS = self.safe_get_node_units(fr"\Data\Streams\{stream}\Input\FLOW\MIXED\{node}")
                        if FLOW_VALUE is not None and FLOW_VALUE != "":
                            flow_values[node] = {
                                "FLOW_VALUE": FLOW_VALUE,
                                "FLOW_UNITS": FLOW_UNITS,
                                "FLOW_BASIS": BASIS
                            }
                stream_data[f"{stream}"]["flow"] = flow_values
            self.data["stream_data"] = stream_data
            print("streams物流数据提取完成")
        except Exception as e:
            print(f"提取streams物流数据时出错: {e}")
            self.data["stream_data"] = {}

    def add_if_not_empty(self, data_dict, key, value, unit_key=None, unit_value=None, basis_key=None, basis_value=None):
        """如果值不为空，则将其添加到字典中"""
        if value is not None and value != "":
            data_dict[key] = value
            if unit_key and unit_value is not None and unit_value != "":
                data_dict[unit_key] = unit_value
            elif basis_key and basis_value is not None and basis_value != "":
                data_dict[basis_key] = basis_value
    def extract_convergence_data(self):
        """提取convergence数据"""
        try:
            convergence_data = {}
            # 收敛-收敛选项
            convergence_data["conv_options"] = {}
            #CONV_NODES = self.get_child_nodes(fr"\Data\Convergence\Convergence")  # 收敛节点
            #CONV_OPT_NODES = self.get_child_nodes(fr"\Data\Convergence\Conv-Options\Input\TEAR_METHOD")  # 收敛-选项
            TEAR_METHOD_VALUE = self.safe_get_node_value(fr"\Data\Convergence\Conv-Options\Input\TEAR_METHOD")  # 收敛-选项-默认方法
            WEG_MAXIT_VALUE = self.safe_get_node_value(fr"\Data\Convergence\Conv-Options\Input\WEG_MAXIT") # 收敛-选项-迭代次数
            self.add_if_not_empty(convergence_data["conv_options"], "tear_method", TEAR_METHOD_VALUE)
            self.add_if_not_empty(convergence_data["conv_options"], "weg_maxit", WEG_MAXIT_VALUE)
            convergence_data["tear_data"] = []
            TEAR_NODES = self.get_child_nodes(fr"\Data\Convergence\Tear\Input\TOL")  # 收敛-撕裂-规定
            for tear_stream in TEAR_NODES:
                tear_stream_value = self.safe_get_node_value(fr"\Data\Convergence\Tear\Input\TOL\{tear_stream}")  # 收敛-撕裂-撕裂流股
                convergence_data["tear_data"].append({
                "tear_stream_name": tear_stream,
                "tear_stream_tol": tear_stream_value
            })
            # # 收敛-收敛
            # convergence_data["conv_data"] = []
            # CONV_NODES = self.get_child_nodes(fr"\Data\Convergence\Convergence")  # 收敛节点
            # for conv in CONV_NODES:
            #     conv_type = self.get_block_type(fr"\Data\Convergence\Convergence\{conv}", 6)  # 收敛类型
            #     tear_stream = []
            #     COMPS_NODES = self.get_child_nodes(fr"\Data\Convergence\Convergence\{conv}\Input\COMPS")  # 收敛-流股
            #     for comp in COMPS_NODES:
            #         STATE = self.safe_get_node_value(
            #             fr"\Data\Convergence\Convergence\{conv}\Input\STATE\{comp}")  # 收敛-状态变量
            #         TOL = self.safe_get_node_value(fr"\Data\Convergence\Convergence\{conv}\Input\TOL\{comp}")  # 收敛-允许误差
            #         tear_stream.append({
            #             "stream_id": comp,
            #             "STATE": STATE,
            #             "TOL": TOL
            #         })
            #     convergence_data["conv_data"].append({
            #         "conv_name": conv,
            #         "conv_type": conv_type,
            #         "tear_stream": tear_stream
            #     })
            # #收敛-序列
            # seq_data = []
            # SEQ_NODES = self.get_child_nodes(fr"\Data\Convergence\Sequence")  # 收敛-序列
            # for seq in SEQ_NODES:
            #     sep_type = self.get_block_type(fr"\Data\Convergence\Sequence\{seq}", 6)  # 序列类型
            #     calc_seq = []
            #     BLOCK_ID_NODES = self.get_child_nodes(fr"\Data\Convergence\Sequence\{seq}\Input\BLOCK_ID")  # 序列-计算顺序-模块
            #     for index, block_id_node in enumerate(BLOCK_ID_NODES):
            #         block_id = self.safe_get_node_value(fr"\Data\Convergence\Sequence\{seq}\Input\BLOCK_ID\{block_id_node}")
            #         block_type = self.safe_get_node_value(fr"\Data\Convergence\Sequence\{seq}\Input\BLOCK_TYPE\{block_id_node}")  # # 序列-计算顺序-模块类型
            #         calc_seq.append({
            #             "seq": index,
            #             "block_id": block_id,
            #             "block_type": block_type
            #         })
            #     seq_data.append({
            #         "sep_name": seq,
            #         "sep_type": sep_type,
            #         "calc_seq": calc_seq
            #     })
            # convergence_data["seq_data"] = seq_data
            self.data["convergence"] = convergence_data
            print(f"提取convergence数据完成")
        except Exception as e:
            print(f"提取convergence数据时出错: {e}")
    def extract_reactions_data(self):
        """提取reactions数据"""
        try:
            reactions_data = {}
            Reactions_NODES = self.get_child_nodes(fr"\Data\Reactions\Reactions")  # 反应
            for Reaction in Reactions_NODES:
                reactions_data[Reaction] = {}
                Reaction_TYPE = self.get_block_type(fr"\Data\Reactions\Reactions\{Reaction}", 6)  # 反应类型
                reactions_data[Reaction]["type"] = Reaction_TYPE
                COEF_NODES = self.get_child_nodes(fr"\Data\Reactions\Reactions\{Reaction}\Input\COEF")  # 反应-化学计量-反应物
                # reactions_data[Reaction]["COEF_DATA"] = {}
                reactions_data[Reaction]["REAC_DATA"] = []
                for REAC_ID in COEF_NODES:
                    reac_data = {}
                    REACTYPE = self.safe_get_node_value(fr"\Data\Reactions\Reactions\{Reaction}\Input\REACTYPE\{REAC_ID}")
                    reac_data["REAC_ID"] = REAC_ID
                    reac_data["REACTYPE"] = REACTYPE
                    reac_data["COEF_DATA"] = {}
                    COEF_SUBNODE = self.aspen.Tree.FindNode(fr"\Data\Reactions\Reactions\{Reaction}\Input\COEF\{REAC_ID}")  # 反应-化学计量-反应物
                    COEF_SUBNODES = self.get_child_nodes(fr"\Data\Reactions\Reactions\{Reaction}\Input\COEF\{REAC_ID}")  # 反应-化学计量-反应物
                    UNIQUE_COEF_SUBNODES = list(dict.fromkeys(COEF_SUBNODES))  # 将得到的二维列表去重
                    # 提取所有组分的name
                    components = self.data.get("components", [])
                    component_cids = [comp['cid'] for comp in components]
                    for i, COEF_MIXED_NODE in enumerate(UNIQUE_COEF_SUBNODES):
                        if COEF_MIXED_NODE[:-6] in component_cids: # 暂不提取自定义组分
                            COEF_MIXED_VALUE = COEF_SUBNODE.Elements(0, i).Value
                            reac_data["COEF_DATA"][COEF_MIXED_NODE[:-6]] = COEF_MIXED_VALUE
                    reac_data["COEF1_DATA"] = {}
                    COEF1_SUBNODE = self.aspen.Tree.FindNode(
                        fr"\Data\Reactions\Reactions\{Reaction}\Input\COEF1\{REAC_ID}")  # 反应-化学计量-反应物
                    COEF1_SUBNODES = self.get_child_nodes(
                        fr"\Data\Reactions\Reactions\{Reaction}\Input\COEF1\{REAC_ID}")  # 反应-化学计量-反应物
                    UNIQUE_COEF1_SUBNODES = list(dict.fromkeys(COEF1_SUBNODES))  # 将得到的二维列表去重
                    for i, COEF1_MIXED_NODE in enumerate(UNIQUE_COEF1_SUBNODES):
                        if COEF1_MIXED_NODE[:-6] in component_cids:  # 暂不提取自定义组分
                            COEF1_MIXED_VALUE = COEF1_SUBNODE.Elements(0, i).Value
                            reac_data["COEF1_DATA"][COEF1_MIXED_NODE[:-6]] = COEF1_MIXED_VALUE
                    # 动力学配置
                    PHASE = self.safe_get_node_value(fr"\Data\Reactions\Reactions\{Reaction}\Input\PHASE\{REAC_ID}")  # 动力学-反应相-类型
                    R_D_RBASIS = self.safe_get_node_value(fr"\Data\Reactions\Reactions\{Reaction}\Input\R_D_RBASIS\{REAC_ID}")  # 动力学-速率基准
                    PRE_EXP = self.safe_get_node_value(fr"\Data\Reactions\Reactions\{Reaction}\Input\PRE_EXP\{REAC_ID}")  # 动力学-反应相-K
                    T_EXP = self.safe_get_node_value(fr"\Data\Reactions\Reactions\{Reaction}\Input\T_EXP\{REAC_ID}")  # 动力学-反应相-n
                    ACT_ENERGY_VALUE = self.safe_get_node_value(fr"\Data\Reactions\Reactions\{Reaction}\Input\ACT_ENERGY\{REAC_ID}")  # 动力学-反应相-E
                    ACT_ENERGY_UNITS = self.safe_get_node_units(fr"\Data\Reactions\Reactions\{Reaction}\Input\ACT_ENERGY\{REAC_ID}")  # 动力学-反应相-E
                    T_REF_VALUE = self.safe_get_node_value(fr"\Data\Reactions\Reactions\{Reaction}\Input\T_REF\{REAC_ID}")  # 动力学-反应相-To
                    T_REF_UNITS = self.safe_get_node_value(fr"\Data\Reactions\Reactions\{Reaction}\Input\T_REF\{REAC_ID}")  # 动力学-反应相-To
                    R_D_CBASIS = self.safe_get_node_value(fr"\Data\Reactions\Reactions\{Reaction}\Input\R_D_CBASIS\{REAC_ID}")  # 动力学-反应相-基准
                    OPT_KINETIC = self.safe_get_node_value(fr"\Data\Reactions\Reactions\{Reaction}\Input\OPT_KINETIC")  # 动力学-使用内置幂定律BUILT/用户自定义SUBROUTINE
                    self.add_if_not_empty(reac_data, "PHASE", PHASE)
                    self.add_if_not_empty(reac_data, "R_D_RBASIS", R_D_RBASIS)
                    self.add_if_not_empty(reac_data, "PRE_EXP", PRE_EXP)
                    self.add_if_not_empty(reac_data, "T_EXP", T_EXP)
                    self.add_if_not_empty(reac_data, "ACT_ENERGY_VALUE", ACT_ENERGY_VALUE, "ACT_ENERGY_UNITS", ACT_ENERGY_UNITS)
                    self.add_if_not_empty(reac_data, "T_REF", T_REF_VALUE, "T_REF_UNITS", T_REF_UNITS)
                    self.add_if_not_empty(reac_data, "R_D_CBASIS", R_D_CBASIS)
                    self.add_if_not_empty(reac_data, "OPT_KINETIC", OPT_KINETIC)
                    reactions_data[Reaction]["REAC_DATA"].append(reac_data)
            self.data["reactions"] = reactions_data
            print(f"提取reactions数据完成")
        except Exception as e:
            print(f"提取reactions数据时出错: {e}")
    def extract_design_specs_data(self):
        """提取设计规定(Design-Spec)数据"""
        try:
            design_specs_data = {}
            # 获取所有设计规定节点
            DS_NODES = self.get_child_nodes(r"\Data\Flowsheeting Options\Design-Spec")

            for design_spec in DS_NODES:
                design_specs_data[design_spec] = {}
                base_path = fr"\Data\Flowsheeting Options\Design-Spec\{design_spec}\Input"
                # 1. 提取定义配置
                # 提取样本变量(FVN_*系列)
                design_specs_data[design_spec]["sampled_variables"] = []
                # 检查样本变量定义
                fvn_variable_path = fr"{base_path}\FVN_VARIABLE"
                # 尝试获取样本变量数组
                try:
                    fvn_variable_nodes = self.get_child_nodes(fvn_variable_path)
                    for fvn_variable in fvn_variable_nodes:
                        sampled_var = {}
                        sampled_var["variable_name"] = fvn_variable
                        # 提取其他FVN_*参数
                        fvn_params = [
                            ("OPT_CATEG", "opt_categ"),
                            ("FVN_STREAM", "stream"),
                            ("FVN_VARIABLE", "variable"),
                            ("FVN_COMPONEN", "component"),
                            ("FVN_SUBS", "substream"),
                            ("FVN_VARTYPE", "variable_type"),
                            ("FVN_PHYS_QTY", "physical_quantity"),
                            ("FVN_UOM", "units"),
                            ("FVN_BLOCK", "block"),
                            ("FVN_EO_NAME", "eo_name"),
                            ("FVN_ID1", "id1"),
                            ("FVN_ID2", "id2"),
                            ("FVN_ID3", "id3"),
                            ("FVN_DESCRIPT", "description"),
                            ("FVN_SENTENCE", "sentence"),
                            ("FVN_PARAMNO", "parameter_number"),
                            ("FVN_ATTRIB", "attribute"),
                            ("FVN_ELEM", "element"),
                            ("FVN_PROPSET", "property_set"),
                            ("FVN_INIT_VAL", "initial_value")
                        ]
                        for fvn_path, key in fvn_params:
                            try:
                                node = self.aspen.Tree.FindNode(fr"{base_path}\{fvn_path}")
                                if node is not None:
                                    subnode = node.Elements(f"{fvn_variable}")
                                    if subnode is not None:
                                        value = subnode.Value
                                        if value is not None:
                                            sampled_var[key] = value
                            except:
                                pass
                        # 只添加有内容的采样变量
                        if sampled_var:
                            design_specs_data[design_spec]["sampled_variables"].append(sampled_var)
                except Exception as e:
                    print(f"提取样本变量时出错: {e}")

                # 2. 提取规定配置
                design_specs_data[design_spec]["objective_function"] = {}
                # 提取表达式1
                expr1 = self.safe_get_node_value(fr"{base_path}\EXPR1")
                self.add_if_not_empty(design_specs_data[design_spec]["objective_function"],
                                      "EXPR1", expr1)
                # 提取容差
                tol = self.safe_get_node_value(fr"{base_path}\TOL")
                self.add_if_not_empty(design_specs_data[design_spec]["objective_function"],
                                      "TOL", tol)

                # 提取表达式2
                expr2 = self.safe_get_node_value(fr"{base_path}\EXPR2")
                self.add_if_not_empty(design_specs_data[design_spec]["objective_function"],
                                      "EXPR2", expr2)

                # 3. 提取操纵变量(VARY_*系列)
                design_specs_data[design_spec]["manipulated_variables"] = []

                # 检查操纵变量定义
                vary_variable_path = fr"{base_path}\VARYVARIABLE"

                # 尝试获取操纵变量值
                try:
                    vary_variable_node = self.aspen.Tree.FindNode(vary_variable_path)

                    # 如果VARYVARIABLE是单个值（不是数组）
                    if vary_variable_node is not None:
                        # 检查是否有值
                        try:
                            vary_value = vary_variable_node.Value
                            if vary_value is not None:
                                manipulated_var = {}
                                manipulated_var["variable_name"] = vary_value

                                # 提取其他VARY_*参数（单值版本）
                                vary_params = [
                                    ("VARYBLOCK", "block"),
                                    ("VARYPHYS_QTY", "physical_quantity"),
                                    ("VARY_VARTYPE", "variable_type"),
                                    ("VARYUOM", "units"),
                                    ("VARYSENTENCE", "sentence"),
                                    ("VARYSTREAM", "stream"),
                                    ("VARYCOMPONEN", "component"),
                                    ("VARYPARAMNO", "parameter_number"),
                                    ("VARYINIT_VAL", "initial_value"),
                                    ("VARYID1", "id1"),
                                    ("VARYID2", "id2"),
                                    ("VARYID3", "id3"),
                                    ("VARYDESCRIPT", "description"),
                                    ("VARYELEM", "element"),
                                    ("VARYEO_NAME", "eo_name"),
                                    ("VARYATTRIB", "attribute"),
                                    ("VARYSUBS", "substream"),
                                    ("VARYPROPSET", "property_set")
                                ]

                                for vary_path, key in vary_params:
                                    try:
                                        value = self.safe_get_node_value(fr"{base_path}\{vary_path}")
                                        if value is not None:
                                            manipulated_var[key] = value
                                    except:
                                        pass

                                # 提取VARYLINE1-4（如果有）
                                for line_num in range(1, 5):
                                    line_key = f"VARYLINE{line_num}"
                                    line_value = self.safe_get_node_value(fr"{base_path}\{line_key}")
                                    if line_value is not None:
                                        manipulated_var[f"line{line_num}"] = line_value

                                design_specs_data[design_spec]["manipulated_variables"].append(manipulated_var)
                        except:
                            # 可能是数组形式
                            mpbp_node = vary_variable_node.Elements("MPBP")
                            if mpbp_node is not None:
                                element_count = mpbp_node.Count

                                # 为每个操纵变量提取信息
                                for i in range(element_count):
                                    manipulated_var = {}

                                    # 提取变量名
                                    try:
                                        var_name = mpbp_node.Elements(0, i).Value
                                        manipulated_var["variable_name"] = var_name
                                    except:
                                        pass

                                    # 提取其他VARY_*参数（数组版本）
                                    vary_params = [
                                        ("VARYBLOCK", "block"),
                                        ("VARYPHYS_QTY", "physical_quantity"),
                                        ("VARY_VARTYPE", "variable_type"),
                                        ("VARYUOM", "units"),
                                        ("VARYSTREAM", "stream"),
                                        ("VARYCOMPONEN", "component"),
                                        ("VARYPARAMNO", "parameter_number"),
                                        ("VARYINIT_VAL", "initial_value"),
                                        ("VARYID1", "id1"),
                                        ("VARYID2", "id2"),
                                        ("VARYID3", "id3"),
                                        ("VARYDESCRIPT", "description"),
                                        ("VARYELEM", "element"),
                                        ("VARYEO_NAME", "eo_name"),
                                        ("VARYATTRIB", "attribute"),
                                        ("VARYSUBS", "substream"),
                                        ("VARYPROPSET", "property_set"),
                                        ("VARYSENTENCE", "sentence")
                                    ]

                                    for vary_path, key in vary_params:
                                        try:
                                            node = self.aspen.Tree.FindNode(fr"{base_path}\{vary_path}")
                                            if node is not None:
                                                mpbp_subnode = node.Elements("MPBP")
                                                if mpbp_subnode is not None and i < mpbp_subnode.Count:
                                                    value = mpbp_subnode.Elements(0, i).Value
                                                    if value is not None:
                                                        manipulated_var[key] = value
                                        except:
                                            pass

                                    # 只添加有内容的操纵变量
                                    if manipulated_var:
                                        design_specs_data[design_spec]["manipulated_variables"].append(manipulated_var)
                except Exception as e:
                    print(f"提取操纵变量时出错: {e}")

                # 提取边界和步长设置
                design_specs_data[design_spec]["bounds"] = {}

                # 提取全局边界
                lower = self.safe_get_node_value(fr"{base_path}\LOWER")
                self.add_if_not_empty(design_specs_data[design_spec]["bounds"],
                                      "LOWER", lower)

                upper = self.safe_get_node_value(fr"{base_path}\UPPER")
                self.add_if_not_empty(design_specs_data[design_spec]["bounds"],
                                      "UPPER", upper)

                # 提取步长设置
                step_size = self.safe_get_node_value(fr"{base_path}\STEP_SIZE")
                self.add_if_not_empty(design_specs_data[design_spec]["bounds"],
                                          "STEP_SIZE", step_size)

                max_step_size = self.safe_get_node_value(fr"{base_path}\MAX_STEP_SIZ")
                self.add_if_not_empty(design_specs_data[design_spec]["bounds"],
                                      "MAX_STEP_SIZ", max_step_size)

                # 提取阈值
                threshold = self.safe_get_node_value(fr"{base_path}\THRESHOLD")
                self.add_if_not_empty(design_specs_data[design_spec]["bounds"],
                                      "THRESHOLD", threshold)

            # 将提取的数据保存到类数据中
            self.data["design_specs"] = design_specs_data

            # 打印提取结果统计
            total_specs = len(design_specs_data)
            print(f"提取设计规定数据完成，共找到 {total_specs} 个设计规定")

            for spec_name, spec_data in design_specs_data.items():
                sampled_count = len(spec_data.get("sampled_variables", []))
                manipulated_count = len(spec_data.get("manipulated_variables", []))
                print(f"  {spec_name}: {sampled_count}个采样变量, {manipulated_count}个操纵变量")

            return design_specs_data

        except Exception as e:
            print(f"提取设计规定数据时出错: {e}")
            import traceback
            traceback.print_exc()
            return None
    def extract_block_Mixer_data(self):
        """提取block-Mixer模块数据"""
        try:
            blocks_Mixer_data = {}
            blocks_Mixer = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "Mixer":
                    blocks_Mixer.append({
                        "name": block['name'],
                        "type": "Mixer"
                    })
            # 规定提取
            for block in blocks_Mixer:
                blocks_Mixer_data[block['name']] = {}
                try:
                    # Mixer-抽取规定
                    blocks_Mixer_data[block['name']]["SPEC_DATA"] = {}
                    PRES_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PRES")  # 闪蒸选项-压力
                    PRES_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PRES")
                    T_EST_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\T_EST")  # 闪蒸选项-温度估值
                    T_EST_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\T_EST")
                    MAXIT = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\MAXIT")  # 闪蒸选项-最大迭代次数
                    TOL = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\TOL")  # 闪蒸选项-容许误差
                    self.add_if_not_empty(blocks_Mixer_data[block['name']]["SPEC_DATA"], "PRES_VALUE", PRES_VALUE, "PRES_UNITS", PRES_UNITS)
                    self.add_if_not_empty(blocks_Mixer_data[block['name']]["SPEC_DATA"], "T_EST_VALUE", T_EST_VALUE, "T_EST_UNITS", T_EST_UNITS)
                    self.add_if_not_empty(blocks_Mixer_data[block['name']]["SPEC_DATA"], "MAXIT_VALUE", MAXIT)
                    self.add_if_not_empty(blocks_Mixer_data[block['name']]["SPEC_DATA"], "TOL_VALUE", TOL)
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}规定数据时出错: {e}")
            print(f"提取blocks模块Mixer所有数据完成")
            self.data["blocks_Mixer_data"] = blocks_Mixer_data
        except Exception as e:
            print(f"提取blocks模块{blocks_Mixer['type']}_{blocks_Mixer['name']}数据时出错: {e}")
    def extract_block_Valve_data(self):
        """提取block-Valve模块数据"""
        try:
            blocks_Valve_data = {}
            blocks_Valve = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "Valve":
                    blocks_Valve.append({
                        "name": block['name'],
                        "type": "Valve"
                    })
            # 规定提取
            for block in blocks_Valve:
                blocks_Valve_data[block['name']] = {}
                try:
                    blocks_Valve_data[block['name']]["JOB_DATA"] = {}
                    MODE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\MODE")  # 作业-计算类型
                    blocks_Valve_data[block['name']]["JOB_DATA"]["MODE"] = MODE
                    if MODE == "ADIAB-FLASH":  # 当前只抽取指定出口压力下绝热闪蒸，可自行添加
                        P_OUT_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\P_OUT")  # 作业-压力规范-出口压力
                        P_OUT_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\P_OUT")  # 作业-压力规范-出口压力
                        NPHASE = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\NPHASE")  # 作业-闪蒸选项-有效相态
                        FLASH_MAXIT = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\FLASH_MAXIT")  # 作业-闪蒸选项-最大迭代次数
                        FLASH_TOL = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\FLASH_TOL")  # 作业-闪蒸选项-容许误差
                        self.add_if_not_empty(blocks_Valve_data[block['name']]["JOB_DATA"], "P_OUT_VALUE", P_OUT_VALUE, "P_OUT_UNITS", P_OUT_UNITS)
                        self.add_if_not_empty(blocks_Valve_data[block['name']]["JOB_DATA"], "NPHASE", NPHASE)
                        self.add_if_not_empty(blocks_Valve_data[block['name']]["JOB_DATA"], "FLASH_MAXIT", FLASH_MAXIT)
                        self.add_if_not_empty(blocks_Valve_data[block['name']]["JOB_DATA"], "FLASH_TOL", FLASH_TOL)
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}数据时出错: {e}")
                    continue
            print(f"提取blocks模块Valve所有数据完成")
            self.data["blocks_Valve_data"] = blocks_Valve_data
        except Exception as e:
            print(f"提取blocks模块{blocks_Valve['type']}_{blocks_Valve['name']}数据时出错: {e}")
    def extract_block_Compr_data(self):
        """提取block-Compr模块数据"""
        try:
            blocks_Compr_data = {}
            blocks_Compr = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "Compr":
                    blocks_Compr.append({
                        "name": block['name'],
                        "type": "Compr"
                    })
            # 规定提取
            for block in blocks_Compr:
                blocks_Compr_data[block['name']] = {}
                try:
                    # Compr-抽取规定、公用工程
                    MODEL_TYPE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\MODEL_TYPE")  # 规定-模型
                    TYPE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\TYPE")  # 规定-类型
                    OPT_SPEC = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\OPT_SPEC")  # 规定-出口规范
                    PRES_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PRES")  # 规定-排放压力
                    PRES_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PRES")
                    UTILITY_ID = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\UTILITY_ID")  # 公用工程(放规定一起)
                    blocks_Compr_data[block['name']]["SPEC_DATA"] = {
                        "MODEL_TYPE": MODEL_TYPE,
                        "TYPE": TYPE,
                    }
                    if PRES_VALUE is not None and PRES_VALUE != "":
                        blocks_Compr_data[block['name']]["SPEC_DATA"]["PRES_VALUE"] = PRES_VALUE
                        blocks_Compr_data[block['name']]["SPEC_DATA"]["PRES_UNITS"] = PRES_UNITS
                    if OPT_SPEC is not None and OPT_SPEC != "":
                        blocks_Compr_data[block['name']]["SPEC_DATA"]["OPT_SPEC"] = OPT_SPEC
                    if UTILITY_ID is not None and UTILITY_ID != "":
                        blocks_Compr_data[block['name']]["SPEC_DATA"]["UTILITY_ID"] = UTILITY_ID
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}数据时出错: {e}")
                    continue
            print(f"提取blocks模块Compr所有数据完成")
            self.data["blocks_Compr_data"] = blocks_Compr_data
        except Exception as e:
            print(f"提取blocks模块{blocks_Compr['type']}_{blocks_Compr['name']}数据时出错: {e}")
    def extract_block_Heater_data(self):
        """提取block-Heater模块数据"""
        try:
            blocks_Heater_data = {}
            blocks_Heater = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "Heater":
                    blocks_Heater.append({
                        "name": block['name'],
                        "type": "Heater"
                    })
            # 规定提取
            for block in blocks_Heater:
                blocks_Heater_data[block['name']] = {}
                try:
                    SPEC_OPT = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\SPEC_OPT")  # 规定-闪蒸计算类型
                    TEMP_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\TEMP")  # 规定-温度
                    TEMP_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\TEMP")
                    DELT_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DELT")  # 规定-温度变化
                    DELT_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DELT")
                    DEGSUP_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DEGSUP")  # 规定-过热度
                    DEGSUP_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DEGSUP")
                    DEGSUB_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DEGSUB")  # 规定-过冷度
                    DEGSUB_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DEGSUB")
                    VFRAC_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\VFRAC")  # 规定-汽相分率
                    PRES_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PRES")  # 规定-压力
                    PRES_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PRES")
                    DUTY_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DUTY")  # 规定-负载
                    DUTY_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DUTY")
                    # UTILITY_ID = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\UTILITY_ID")  # 公用工程
                    blocks_Heater_data[block['name']]["SPEC_DATA"] = {
                        "SPEC_OPT": SPEC_OPT
                    }
                    if TEMP_VALUE is not None and TEMP_VALUE != "":
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["TEMP_VALUE"] = TEMP_VALUE
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["TEMP_UNITS"] = TEMP_UNITS
                    if DELT_VALUE is not None and DELT_VALUE != "":
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["DELT_VALUE"] = DELT_VALUE
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["DELT_UNITS"] = DELT_UNITS
                    if DEGSUP_VALUE is not None and DEGSUP_VALUE != "":
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["DEGSUP_VALUE"] = DEGSUP_VALUE
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["DEGSUP_UNITS"] = DEGSUP_UNITS
                    if DEGSUB_VALUE is not None and DEGSUB_VALUE != "":
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["DEGSUB_VALUE"] = DEGSUB_VALUE
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["DEGSUB_UNITS"] = DEGSUB_UNITS
                    if VFRAC_VALUE is not None and VFRAC_VALUE != "":
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["VFRAC_VALUE"] = VFRAC_VALUE
                    if PRES_VALUE is not None and PRES_VALUE != "":
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["PRES_VALUE"] = PRES_VALUE
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["PRES_UNITS"] = PRES_UNITS
                    if DUTY_VALUE is not None and DUTY_VALUE != "":
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["DUTY_VALUE"] = DUTY_VALUE
                        blocks_Heater_data[block['name']]["SPEC_DATA"]["DUTY_UNITS"] = DUTY_UNITS
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}数据时出错: {e}")
                    continue
            print(f"提取blocks模块Heater所有数据完成")
            self.data["blocks_Heater_data"] = blocks_Heater_data
        except Exception as e:
            print(f"提取blocks模块{blocks_Heater['type']}_{blocks_Heater['name']}数据时出错: {e}")
    def extract_block_Pump_data(self):
        """提取block-Pump模块数据"""
        try:
            blocks_Pump_data = {}
            blocks_Pump = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "Pump":
                    blocks_Pump.append({
                        "name": block['name'],
                        "type": "Pump"
                    })
            # 规定提取
            for block in blocks_Pump:
                blocks_Pump_data[block['name']] = {}
                try:
                    PUMP_TYPE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PUMP_TYPE")  # 规定-模型
                    OPT_SPEC = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\OPT_SPEC")  # 规定-出口规范
                    PRES_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PRES")  # 规定-排放压力
                    PRES_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PRES")
                    UTILITY_ID = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\UTILITY_ID")  # 公用工程
                    blocks_Pump_data[block['name']]["SPEC_DATA"] = {
                        "PUMP_TYPE": PUMP_TYPE
                    }
                    if PRES_VALUE is not None and PRES_VALUE != "":
                        blocks_Pump_data[block['name']]["SPEC_DATA"]["PRES_VALUE"] = PRES_VALUE
                        blocks_Pump_data[block['name']]["SPEC_DATA"]["PRES_UNITS"] = PRES_UNITS
                    if OPT_SPEC is not None and OPT_SPEC != "":
                        blocks_Pump_data[block['name']]["SPEC_DATA"]["OPT_SPEC"] = OPT_SPEC
                    if UTILITY_ID is not None and UTILITY_ID != "":
                        blocks_Pump_data[block['name']]["SPEC_DATA"]["UTILITY_ID"] = UTILITY_ID
                    # blocks_Pump_data[block['name']]["SPEC_DATA"] = {
                    #     "PUMP_TYPE": PUMP_TYPE,
                    #     "PRES_VALUE": PRES_VALUE,
                    #     "PRES_UNITS": PRES_UNITS,
                    #     "UTILITY_ID": UTILITY_ID
                    # }
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}数据时出错: {e}")
                    continue
            print(f"提取blocks模块Pump所有数据完成")
            self.data["blocks_Pump_data"] = blocks_Pump_data
        except Exception as e:
            print(f"提取blocks模块{blocks_Pump['type']}_{blocks_Pump['name']}数据时出错: {e}")
    def extract_block_RStoic_data(self):
        """提取block-RStoic模块数据"""
        try:
            blocks_RStoic_data = {}
            blocks_RStoic = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "RStoic":
                    blocks_RStoic.append({
                        "name": block['name'],
                        "type": "RStoic"
                    })
            # 规定提取
            for block in blocks_RStoic:
                blocks_RStoic_data[block['name']] = {}
                try:
                    # 规定提取
                    SPEC_OPT = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\SPEC_OPT")  # 规定-闪蒸计算类型
                    TEMP_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\TEMP")  # 规定-温度
                    TEMP_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\TEMP")
                    DELT_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DELT")  # 规定-温度变化
                    DELT_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DELT")
                    VFRAC_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\VFRAC")  # 规定-汽相分率
                    PRES_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PRES")  # 规定-压力
                    PRES_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PRES")
                    DUTY_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DUTY")  # 规定-负载
                    DUTY_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DUTY")
                    PHASE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PHASE")  # 规定-有效相态
                    UTILITY_ID = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\UTILITY_ID")  # 公用工程
                    blocks_RStoic_data[block['name']]["SPEC_DATA"] = {
                        "SPEC_OPT": SPEC_OPT
                    }
                    if TEMP_VALUE is not None and TEMP_VALUE != "":
                        blocks_RStoic_data[block['name']]["SPEC_DATA"]["TEMP_VALUE"] = TEMP_VALUE
                        blocks_RStoic_data[block['name']]["SPEC_DATA"]["TEMP_UNITS"] = TEMP_UNITS
                    if DELT_VALUE is not None and DELT_VALUE != "":
                        blocks_RStoic_data[block['name']]["SPEC_DATA"]["DELT_VALUE"] = DELT_VALUE
                        blocks_RStoic_data[block['name']]["SPEC_DATA"]["DELT_UNITS"] = DELT_UNITS
                    if VFRAC_VALUE is not None and VFRAC_VALUE != "":
                        blocks_RStoic_data[block['name']]["SPEC_DATA"]["VFRAC_VALUE"] = VFRAC_VALUE
                    if PRES_VALUE is not None and PRES_VALUE != "":
                        blocks_RStoic_data[block['name']]["SPEC_DATA"]["PRES_VALUE"] = PRES_VALUE
                        blocks_RStoic_data[block['name']]["SPEC_DATA"]["PRES_UNITS"] = PRES_UNITS
                    if DUTY_VALUE is not None and DUTY_VALUE != "":
                        blocks_RStoic_data[block['name']]["SPEC_DATA"]["DUTY_VALUE"] = DUTY_VALUE
                        blocks_RStoic_data[block['name']]["SPEC_DATA"]["DUTY_UNITS"] = DUTY_UNITS
                    if PHASE is not None and PHASE != "":
                        blocks_RStoic_data[block['name']]["SPEC_DATA"]["PHASE"] = PHASE
                    if UTILITY_ID is not None and UTILITY_ID != "":
                        blocks_RStoic_data[block['name']]["SPEC_DATA"]["UTILITY_ID"] = UTILITY_ID
                    # 反应提取
                    SERIES = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\SERIES")  # 反应-反应连续发生
                    blocks_RStoic_data[block['name']]["REAC_DATA"] = {
                        "SERIES": SERIES
                    }
                    blocks_RStoic_data[block['name']]["REAC_DATA"]["REAC"] = []
                    KEY_SSID_NODES = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Input\KEY_SSID")  # 反应-反应编号
                    for SSID in KEY_SSID_NODES:
                        CONV = self.safe_get_node_value(
                            fr"\Data\Blocks\{block['name']}\Input\CONV\{SSID}")  # 反应-转化率
                        KEY_CID = self.safe_get_node_value(
                            fr"\Data\Blocks\{block['name']}\Input\KEY_CID\{SSID}")  # 反应-组分转化率
                        OPT_EXT_CONV = self.safe_get_node_value(
                            fr"\Data\Blocks\{block['name']}\Input\OPT_EXT_CONV\{SSID}")  # 反应-规范类型
                        EXTENT = self.safe_get_node_value(
                            fr"\Data\Blocks\{block['name']}\Input\EXTENT\{SSID}")  # 反应-摩尔反应进度
                        COEF_DATA = {}
                        COEF_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block['name']}\Input\COEF\{SSID}")  # 反应-化学计量-反应物
                        COEF_MIXED_NODE = self.get_child_nodes(
                            fr"\Data\Blocks\{block['name']}\Input\COEF\{SSID}")  # 反应-化学计量-反应物
                        UNIQUE_COEF_MIXED_NODES = list(dict.fromkeys(COEF_MIXED_NODE)) # 将得到的二维列表去重
                        for i, MIXED_NODE in enumerate(UNIQUE_COEF_MIXED_NODES):
                            COEF_MIXED_VALUE = COEF_NODE.Elements(0, i).Value
                            COEF_DATA[MIXED_NODE[:-6]] = COEF_MIXED_VALUE #最后六位 MIXED无需保留
                        # blocks_RStoic_data[block['name']]["REAC_DATA"][SSID]["COEF1_DATA"] = {}
                        COEF1_DATA = {}
                        COEF1_NODE = self.aspen.Tree.FindNode(fr"\Data\Blocks\{block['name']}\Input\COEF1\{SSID}")  # 反应-化学计量-反应物
                        COEF1_MIXED_NODE = self.get_child_nodes(
                            fr"\Data\Blocks\{block['name']}\Input\COEF1\{SSID}")  # 反应-化学计量-反应物
                        UNIQUE_COEF1_MIXED_NODES = list(dict.fromkeys(COEF1_MIXED_NODE)) # 将得到的二维列表去重
                        for i, MIXED_NODE in enumerate(UNIQUE_COEF1_MIXED_NODES):
                            COEF1_MIXED_VALUE = COEF1_NODE.Elements(0, i).Value
                            # blocks_RStoic_data[block['name']]["REAC_DATA"][SSID]["COEF1_DATA"][MIXED_NODE] = COEF1_MIXED_VALUE
                            COEF1_DATA[MIXED_NODE[:-6]] = COEF1_MIXED_VALUE #最后六位 MIXED无需保留
                        blocks_RStoic_data[block['name']]["REAC_DATA"]["REAC"].append({
                            "KEY_SSID": SSID,
                            "CONV": CONV,
                            "KEY_CID": KEY_CID,
                            "OPT_EXT_CONV": OPT_EXT_CONV,
                            "EXTENT": EXTENT,
                            "COEF_DATA": COEF_DATA,
                            "COEF1_DATA": COEF1_DATA
                        })
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}数据时出错: {e}")
                    continue
            print(f"提取blocks模块RStoic所有数据完成")
            self.data["blocks_RStoic_data"] = blocks_RStoic_data
        except Exception as e:
            print(f"提取blocks模块{blocks_RStoic['type']}_{blocks_RStoic['name']}数据时出错: {e}")
    def extract_block_RPlug_data(self):
        """提取block-RPlug模块数据"""
        try:
            blocks_RPlug_data = {}
            blocks_RPlug = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "RPlug":
                    blocks_RPlug.append({
                        "name": block['name'],
                        "type": "RPlug"
                    })
            # 规定提取
            for block in blocks_RPlug:
                blocks_RPlug_data[block['name']] = {}
                try:
                    TYPE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\TYPE")  # 规定-反应器类型
                    OPT_TSPEC = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\OPT_TSPEC")  # 规定-操作条件
                    blocks_RPlug_data[block['name']]["SPEC_DATA"] = {
                        "TYPE": TYPE,
                        "OPT_TSPEC": OPT_TSPEC
                    }
                    if OPT_TSPEC == "CONST-TEMP":
                        REAC_TEMP = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\REAC_TEMP")  # 规定-反应器类型-操作条件-指定反应器温度
                        blocks_RPlug_data[block['name']]["SPEC_DATA"]["REAC_TEMP"] = REAC_TEMP
                    if OPT_TSPEC == "TEMP-PROF":
                        SPEC_TEMP_NODES = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Input\SPEC_TEMP")  # 规定-反应器类型-操作条件-温度分布-温度
                        SPEC_TEMP_DATA = {}
                        for SPEC_TEMP in SPEC_TEMP_NODES:
                            SPEC_TEMP_DATA[SPEC_TEMP] = {}
                            SPEC_TEMP_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\SPEC_TEMP\{SPEC_TEMP}")
                            SPEC_TEMP_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\SPEC_TEMP\{SPEC_TEMP}")
                            LOC_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\LOC\{SPEC_TEMP}")  # 规定-反应器类型-操作条件-温度分布-位置
                            if SPEC_TEMP_VALUE is not None and SPEC_TEMP_VALUE != "":
                                SPEC_TEMP_DATA[SPEC_TEMP]["SPEC_TEMP_VALUE"] = SPEC_TEMP_VALUE,
                                SPEC_TEMP_DATA[SPEC_TEMP]["SPEC_TEMP_UNITS"] = SPEC_TEMP_UNITS,
                            if LOC_VALUE is not None and LOC_VALUE != "":
                                SPEC_TEMP_DATA[SPEC_TEMP]["LOC_VALUE"] = LOC_VALUE,
                        blocks_RPlug_data[block['name']]["SPEC_DATA"] = SPEC_TEMP_DATA
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}规定数据时出错: {e}")
                    continue
                try:
                    # 配置提取
                    blocks_RPlug_data[block['name']]["CONFIG_DATA"] = {}
                    CHK_NTUBE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\CHK_NTUBE")  # 配置-多管反应器
                    NTUBE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\NTUBE")  # 配置-多管反应器-管数
                    LENGTH = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\LENGTH")  # 配置-反应器维度-长度
                    DIAM = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DIAM")  # 配置-反应器维度-直径
                    PHASE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PHASE")  # 配置-有效相-工艺流股
                    blocks_RPlug_data[block['name']]["CONFIG_DATA"]["PHASE"] = PHASE
                    if CHK_NTUBE is not None and CHK_NTUBE != "":
                        blocks_RPlug_data[block['name']]["CONFIG_DATA"]["CHK_NTUBE"] = CHK_NTUBE
                    if NTUBE is not None and NTUBE != "":
                        blocks_RPlug_data[block['name']]["CONFIG_DATA"]["NTUBE"] = NTUBE
                    if LENGTH is not None and LENGTH != "":
                        blocks_RPlug_data[block['name']]["CONFIG_DATA"]["LENGTH"] = LENGTH
                    if DIAM is not None and DIAM != "":
                        blocks_RPlug_data[block['name']]["CONFIG_DATA"]["DIAM"] = DIAM
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}配置数据时出错: {e}")
                    continue
                try:
                    #反应提取
                    REACSYS = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\REACSYS")  # 反应-反应体系
                    RXN_ID_NODES = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Input\RXN_ID")  # 反应-所选反应集
                    RXN_ID_DATA = {}
                    for RXN_ID in RXN_ID_NODES:
                        RXN_ID_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\RXN_ID\{RXN_ID}")
                        RXN_ID_DATA[RXN_ID] = RXN_ID_VALUE
                    blocks_RPlug_data[block['name']]["REAC_DATA"] = {
                        "REACSYS": REACSYS,
                        "RXN_ID": RXN_ID_DATA
                    }
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}反应配置时出错: {e}")
                    continue
                try:
                    # 压力提取
                    PRES_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PRES")  # 压力-进口压力
                    PRES_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PRES")  # 压力-进口压力
                    OPT_PDROP = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\OPT_PDROP ")  # 压力-通过反应器的压降
                    PDROP_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PDROP ")  # 压力-压降-工艺流股
                    PDROP_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PDROP ")  # 压力-压降-工艺流股
                    ROUGHNESS_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\ROUGHNESS ")  # 压力-摩擦关联式-粗糙度
                    ROUGHNESS_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\ROUGHNESS ")  # 压力-摩擦关联式-粗糙度
                    DP_FCOR = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DP_FCOR")  # 压力-摩擦关联式-压降关联式
                    DP_MULT = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DP_MULT")  # 压力-摩擦关联式-压降比例因子
                    blocks_RPlug_data[block['name']]["PRES_DATA"] = {
                        "OPT_PDROP": OPT_PDROP
                    }
                    if PRES_VALUE is not None and PRES_VALUE != "":
                        blocks_RPlug_data[block['name']]["PRES_DATA"]["PRES_VALUE"] = PRES_VALUE
                        blocks_RPlug_data[block['name']]["PRES_DATA"]["PRES_UNITS"] = PRES_UNITS
                    if PDROP_VALUE is not None and PDROP_VALUE != "":
                        blocks_RPlug_data[block['name']]["PRES_DATA"]["PDROP_VALUE"] = PDROP_VALUE
                        blocks_RPlug_data[block['name']]["PRES_DATA"]["PDROP_UNITS"] = PDROP_UNITS
                    if ROUGHNESS_VALUE is not None and ROUGHNESS_VALUE != "":
                        blocks_RPlug_data[block['name']]["PRES_DATA"]["ROUGHNESS_VALUE"] = ROUGHNESS_VALUE
                        blocks_RPlug_data[block['name']]["PRES_DATA"]["ROUGHNESS_UNITS"] = ROUGHNESS_UNITS
                    if DP_FCOR is not None and DP_FCOR != "":
                        blocks_RPlug_data[block['name']]["PRES_DATA"]["DP_FCOR"] = DP_FCOR
                    if DP_MULT is not None and DP_MULT != "":
                        blocks_RPlug_data[block['name']]["PRES_DATA"]["DP_MULT"] = DP_MULT
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}压力数据时出错: {e}")
                    continue
                try:
                    #催化剂
                    blocks_RPlug_data[block['name']]["CAT_DATA"] = {}
                    CAT_PRESENT = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\CAT_PRESENT")  # 催化剂-反应器内的催化剂
                    IGN_CAT_VOL = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\IGN_CAT_VOL")  # 催化剂-忽略催化器体积
                    BED_VOIDAGE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\BED_VOIDAGE")  # 催化剂-规定-床空隙率
                    CAT_RHO_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\CAT_RHO")  # 催化剂-规定-颗粒密度
                    CAT_RHO_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\CAT_RHO")  # 催化剂-规定-颗粒密度
                    CATWT_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\CATWT")  # 催化剂-规定-催化剂装填
                    CATWT_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\CATWT")  # 催化剂-规定-催化剂装填
                    if CAT_PRESENT is not None and CAT_PRESENT != "":
                        blocks_RPlug_data[block['name']]["CAT_DATA"]["CAT_PRESENT"] = CAT_PRESENT
                    if IGN_CAT_VOL is not None and IGN_CAT_VOL != "":
                        blocks_RPlug_data[block['name']]["CAT_DATA"]["IGN_CAT_VOL"] = IGN_CAT_VOL
                    if BED_VOIDAGE is not None and BED_VOIDAGE != "":
                        blocks_RPlug_data[block['name']]["CAT_DATA"]["BED_VOIDAGE"] = BED_VOIDAGE
                    if CAT_RHO_VALUE is not None and CAT_RHO_VALUE != "":
                        blocks_RPlug_data[block['name']]["CAT_DATA"]["CAT_RHO_VALUE"] = CAT_RHO_VALUE
                        blocks_RPlug_data[block['name']]["CAT_DATA"]["CAT_RHO_UNITS"] = CAT_RHO_UNITS
                    if CATWT_VALUE is not None and CATWT_VALUE != "":
                        blocks_RPlug_data[block['name']]["CAT_DATA"]["CATWT_VALUE"] = CATWT_VALUE
                        blocks_RPlug_data[block['name']]["CAT_DATA"]["CATWT_UNITS"] = CATWT_UNITS
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}催化剂数据时出错: {e}")
                    continue
            print(f"提取blocks模块RPlug所有数据完成")
            self.data["blocks_RPlug_data"] = blocks_RPlug_data
        except Exception as e:
            print(f"提取blocks模块{blocks_RPlug['type']}_{blocks_RPlug['name']}数据时出错: {e}")
    def extract_block_Flash2_data(self):
        """提取block-Flash2模块数据"""
        try:
            blocks_Flash2_data = {}
            blocks_Flash2 = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "Flash2":
                    blocks_Flash2.append({
                        "name": block['name'],
                        "type": "Flash2"
                    })
            # 规定提取
            for block in blocks_Flash2:
                blocks_Flash2_data[block['name']] = {}
                try:
                    SPEC_OPT = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\SPEC_OPT")  # 规定-闪蒸计算类型
                    TEMP_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\TEMP")  # 规定-温度
                    TEMP_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\TEMP")
                    DELT_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DELT")  # 规定-温度变化
                    DELT_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DELT")
                    VFRAC_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\VFRAC")  # 规定-汽相分率
                    VFRAC_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\VFRAC")
                    PRES_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PRES")  # 规定-压力
                    PRES_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PRES")
                    DUTY_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DUTY")  # 规定-负载
                    DUTY_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DUTY")
                    UTILITY_ID = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\UTILITY_ID")  # 公用工程
                    blocks_Flash2_data[block['name']]["SPEC_DATA"] = {
                        "SPEC_OPT": SPEC_OPT
                    }
                    if TEMP_VALUE is not None and TEMP_VALUE != "":
                        blocks_Flash2_data[block['name']]["SPEC_DATA"]["TEMP_VALUE"] = TEMP_VALUE
                        blocks_Flash2_data[block['name']]["SPEC_DATA"]["TEMP_UNITS"] = TEMP_UNITS
                    if DELT_VALUE is not None and DELT_VALUE != "":
                        blocks_Flash2_data[block['name']]["SPEC_DATA"]["DELT_VALUE"] = DELT_VALUE
                        blocks_Flash2_data[block['name']]["SPEC_DATA"]["DELT_UNITS"] = DELT_UNITS
                    if VFRAC_VALUE is not None and VFRAC_VALUE != "":
                        blocks_Flash2_data[block['name']]["SPEC_DATA"]["VFRAC_VALUE"] = VFRAC_VALUE
                        blocks_Flash2_data[block['name']]["SPEC_DATA"]["VFRAC_UNITS"] = VFRAC_UNITS
                    if PRES_VALUE is not None and PRES_VALUE != "":
                        blocks_Flash2_data[block['name']]["SPEC_DATA"]["PRES_VALUE"] = PRES_VALUE
                        blocks_Flash2_data[block['name']]["SPEC_DATA"]["PRES_UNITS"] = PRES_UNITS
                    if DUTY_VALUE is not None and DUTY_VALUE != "":
                        blocks_Flash2_data[block['name']]["SPEC_DATA"]["DUTY_VALUE"] = DUTY_VALUE
                        blocks_Flash2_data[block['name']]["SPEC_DATA"]["DUTY_UNITS"] = DUTY_UNITS
                    if UTILITY_ID is not None and UTILITY_ID != "":
                        blocks_Flash2_data[block['name']]["SPEC_DATA"]["UTILITY_ID"] = UTILITY_ID
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}数据时出错: {e}")
                    continue
            print(f"提取blocks模块Flash2所有数据完成")
            self.data["blocks_Flash2_data"] = blocks_Flash2_data
        except Exception as e:
            print(f"提取blocks模块{blocks_Flash2['type']}_{blocks_Flash2['name']}数据时出错: {e}")
    def extract_block_Decanter_data(self):
        """提取Decanter模块数据"""
        try:
            blocks_Decanter_data = {}
            blocks_Decanter = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "Decanter":
                    blocks_Decanter.append({
                        "name": block['name'],
                        "type": "Decanter"
                    })
            # 规定提取
            for block in blocks_Decanter:
                blocks_Decanter_data[block['name']] = {}
                try:
                    TEMP_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\TEMP")  # 规定-倾析器规范-温度
                    TEMP_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\TEMP")
                    PRES_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PRES")  # 规定-倾析器规范-压力
                    PRES_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PRES")
                    DUTY_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DUTY")  # 规定-倾析器规范-负荷
                    DUTY_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DUTY")
                    L2_CUTOFF = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\L2_CUTOFF") # 规定-第二液相的组分摩尔分率
                    L2_COMPS_NODES = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Input\L2_COMPS") # 规定-第二液相的关键组分
                    blocks_Decanter_data[block['name']]["SPEC_DATA"] = {}
                    if TEMP_VALUE is not None and TEMP_VALUE != "":
                        blocks_Decanter_data[block['name']]["SPEC_DATA"]["TEMP_VALUE"] = TEMP_VALUE
                        blocks_Decanter_data[block['name']]["SPEC_DATA"]["TEMP_UNITS"] = TEMP_UNITS
                    if PRES_VALUE is not None and PRES_VALUE != "":
                        blocks_Decanter_data[block['name']]["SPEC_DATA"]["PRES_VALUE"] = PRES_VALUE
                        blocks_Decanter_data[block['name']]["SPEC_DATA"]["PRES_UNITS"] = PRES_UNITS
                    if DUTY_VALUE is not None and DUTY_VALUE != "":
                        blocks_Decanter_data[block['name']]["SPEC_DATA"]["DUTY_VALUE"] = DUTY_VALUE
                        blocks_Decanter_data[block['name']]["SPEC_DATA"]["DUTY_UNITS"] = DUTY_UNITS
                    if L2_CUTOFF is not None and L2_CUTOFF != "":
                        blocks_Decanter_data[block['name']]["SPEC_DATA"]["L2_CUTOFF"] = L2_CUTOFF
                    blocks_Decanter_data[block['name']]["SPEC_DATA"]["L2_COMPS"] = []
                    for L2_COMPS in L2_COMPS_NODES:
                        L2_COMPS_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\L2_COMPS\{L2_COMPS}")
                        blocks_Decanter_data[block['name']]["SPEC_DATA"]["L2_COMPS"].append(L2_COMPS_VALUE)
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}数据时出错: {e}")
                    continue
            print(f"提取blocks模块Decanter所有数据完成")
            self.data["blocks_Decanter_data"] = blocks_Decanter_data
        except Exception as e:
            print(f"提取blocks模块{blocks_Decanter['type']}_{blocks_Decanter['name']}数据时出错: {e}")
    def extract_block_Sep_data(self):
        """提取block-Sep模块数据"""
        try:
            blocks_Sep_data = {}
            blocks_Sep = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "Sep":
                    blocks_Sep.append({
                        "name": block['name'],
                        "type": "Sep"
                    })
            # 规定提取
            for block in blocks_Sep:
                blocks_Sep_data[block['name']] = {}
                try:
                    blocks_Sep_data[block['name']]["SPEC_DATA"] = {}
                    FLOW_NODES = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Input\FLOWBASIS")
                    for FLOW in FLOW_NODES:
                        blocks_Sep_data[block['name']]["SPEC_DATA"][FLOW] = []
                        # 提取所有组分ID
                        components = self.data.get("components", [])
                        component_cids = [comp['cid'] for comp in components]
                        COMP_ID_NODES = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Input\FLOWBASIS\{FLOW}\MIXED")
                        for COMP_ID in COMP_ID_NODES:
                            if COMP_ID in component_cids:  # 自定义组分的配置不要提取
                                FLOW_COMP_DATA = {"COMP_ID": COMP_ID}
                                FLOWBASIS = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\FLOWBASIS\{FLOW}\MIXED\{COMP_ID}") # 规定-出口流股条件-基准
                                FRACS = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\FRACS\{FLOW}\MIXED\{COMP_ID}")  # 规定-出口流股条件-规定-分流分率
                                FLOWS_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\FLOWS\{FLOW}\MIXED\{COMP_ID}")  # 规定-出口流股条件-规定-流量
                                FLOWS_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\FRACS\{FLOW}\MIXED\{COMP_ID}")  # 规定-出口流股条件-规定-流量
                                FLOWS_BASIS = self.get_block_type(fr"\Data\Blocks\{block['name']}\Input\FRACS\{FLOW}\MIXED\{COMP_ID}", 13)  # 规定-出口流股条件-规定-流量
                                self.add_if_not_empty(FLOW_COMP_DATA, "FLOWBASIS", FLOWBASIS)
                                self.add_if_not_empty(FLOW_COMP_DATA, "FRACS", FRACS)
                                self.add_if_not_empty(FLOW_COMP_DATA, "FLOWS_VALUE", FLOWS_VALUE, "FLOWS_UNITS", FLOWS_UNITS, "FLOWS_BASIS", FLOWS_BASIS)
                                blocks_Sep_data[block['name']]["SPEC_DATA"][FLOW].append(FLOW_COMP_DATA)
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}数据时出错: {e}")
                    continue
            print(f"提取blocks模块Sep所有数据完成")
            self.data["blocks_Sep_data"] = blocks_Sep_data
        except Exception as e:
            print(f"提取blocks模块{blocks_Sep['type']}_{blocks_Sep['name']}数据时出错: {e}")
    def extract_block_Sep2_data(self):
        """提取block-Sep2模块数据"""
        try:
            blocks_Sep2_data = {}
            blocks_Sep2 = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "Sep2":
                    blocks_Sep2.append({
                        "name": block['name'],
                        "type": "Sep2"
                    })
            # 规定提取
            for block in blocks_Sep2:
                blocks_Sep2_data[block['name']] = {}
                try:
                    blocks_Sep2_data[block['name']]["SPEC_DATA"] = {}
                    FLOW_NODES = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Input\FLOWBASIS\MIXED") #出口流股
                    for FLOW in FLOW_NODES:
                        blocks_Sep2_data[block['name']]["SPEC_DATA"][FLOW] = []
                        # 提取所有组分ID
                        components = self.data.get("components", [])
                        component_cids = [comp['cid'] for comp in components]
                        COMP_ID_NODES = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Input\FLOWBASIS\MIXED\{FLOW}")
                        for COMP_ID in COMP_ID_NODES:
                            if COMP_ID in component_cids:  # 自定义组分的配置不要提取
                                FLOW_COMP_DATA = {"COMP_ID": COMP_ID}
                                FLOWBASIS = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\FLOWBASIS\MIXED\{FLOW}\{COMP_ID}") # 规定-出口流股条件-基准
                                FRACS = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\FRACS\MIXED\{FLOW}\{COMP_ID}")  # 规定-出口流股条件-规定-分流分率
                                FLOWS_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\FLOWS\MIXED\{FLOW}\{COMP_ID}")  # 规定-出口流股条件-规定-流量
                                FLOWS_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\FRACS\MIXED\{FLOW}\{COMP_ID}")  # 规定-出口流股条件-规定-流量
                                FLOWS_BASIS = self.get_block_type(fr"\Data\Blocks\{block['name']}\Input\FRACS\MIXED\{FLOW}\{COMP_ID}", 13)  # 规定-出口流股条件-规定-流量
                                self.add_if_not_empty(FLOW_COMP_DATA, "FLOWBASIS", FLOWBASIS)
                                self.add_if_not_empty(FLOW_COMP_DATA, "FRACS", FRACS)
                                self.add_if_not_empty(FLOW_COMP_DATA, "FLOWS_VALUE", FLOWS_VALUE, "FLOWS_UNITS", FLOWS_UNITS, "FLOWS_BASIS", FLOWS_BASIS)
                                blocks_Sep2_data[block['name']]["SPEC_DATA"][FLOW].append(FLOW_COMP_DATA)
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}数据时出错: {e}")
                    continue
            print(f"提取blocks模块Sep2所有数据完成")
            self.data["blocks_Sep2_data"] = blocks_Sep2_data
        except Exception as e:
            print(f"提取blocks模块blocks_Sep2数据时出错: {e}")
    def extract_block_DSTWU_data(self):
        """提取block-DSTWU模块数据"""
        try:
            blocks_DSTWU_data = {}
            blocks_DSTWU = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "DSTWU":
                    blocks_DSTWU.append({
                        "name": block['name'],
                        "type": "DSTWU"
                    })
            # 规定提取
            for block in blocks_DSTWU:
                blocks_DSTWU_data[block['name']] = {}
                try:
                    SPEC_DATA = {}
                    # 塔规范参数
                    OPT_NTRR = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\OPT_NTRR")  # 塔规范-选择RR或NSTAGE
                    self.add_if_not_empty(SPEC_DATA, "OPT_NTRR", OPT_NTRR)
                    RR = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\RR")  # 塔规范-回流比
                    self.add_if_not_empty(SPEC_DATA, "RR", RR)
                    NSTAGE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\NSTAGE")  # 塔规范-塔板数
                    self.add_if_not_empty(SPEC_DATA, "NSTAGE", NSTAGE)
                    PTOP = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PTOP")  # 压力-塔顶压力
                    PTOP_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PTOP")  # 压力-塔顶压力
                    self.add_if_not_empty(SPEC_DATA, "PTOP", PTOP,"PTOP_UNITS", PTOP_UNITS)
                    PBOT = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PBOT")  # 压力-塔底压力
                    PBOT_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PBOT")  # 压力-塔底压力
                    self.add_if_not_empty(SPEC_DATA, "PBOT", PBOT, "PBOT_UNITS", PBOT_UNITS)
                    OPT_RDV = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\OPT_RDV")  # 冷凝器规范-选择LIQUID/VAPOR/VAPLIQ
                    self.add_if_not_empty(SPEC_DATA, "OPT_RDV", OPT_RDV)
                    RDV = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\RDV")  # 冷凝器规范-汽相分率
                    self.add_if_not_empty(SPEC_DATA, "RDV", RDV)
                    LIGHTKEY = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\LIGHTKEY")  # 关键组分-轻关键组分
                    self.add_if_not_empty(SPEC_DATA, "LIGHTKEY", LIGHTKEY)
                    RECOVL = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\RECOVL")  # 关键组分-轻关键组分回收率
                    self.add_if_not_empty(SPEC_DATA,"RECOVL", RECOVL)
                    RECOVH = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\RECOVH")  # 关键组分-重关键组分回收率
                    self.add_if_not_empty(SPEC_DATA,"RECOVH", RECOVH)
                    HEAVYKEY = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\HEAVYKEY")  # 关键组分-重关键组分
                    self.add_if_not_empty(SPEC_DATA,"HEAVYKEY", HEAVYKEY)
                    blocks_DSTWU_data[block['name']]["SPEC_DATA"]= SPEC_DATA
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}数据时出错: {e}")
                    continue
            print(f"提取blocks模块DSTWU所有数据完成")
            self.data["blocks_DSTWU_data"] = blocks_DSTWU_data
        except Exception as e:
            print(f"提取blocks模块blocks_DSTWU数据时出错: {e}")
    def extract_block_RadFrac_data(self):
        """提取block-RadFrac模块数据"""
        try:
            blocks_RadFrac_data = {}
            blocks_RadFrac = []
            blocks = self.data.get("blocks", [])
            for block in blocks:
                if block['type'] == "RadFrac":
                    blocks_RadFrac.append({
                        "name": block['name'],
                        "type": "RadFrac"
                    })
            # 规定提取
            for block in blocks_RadFrac:
                blocks_RadFrac_data[block['name']] = {}
                try:
                    #配置抽取
                    CALC_MODE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\CALC_MODE")  # 配置-计算类型
                    NSTAGE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\NSTAGE")  # 配置-塔板数
                    CONDENSER = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\CONDENSER") #配置-冷凝器
                    REBOILER = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\REBOILER") #配置-再沸器
                    NO_PHASE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\NO_PHASE") #配置-有效相态
                    BLKOPFREWAT = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\BLKOPFREWAT") #配置-有效相态
                    CONV_METH = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\CONV_METH") #配置-收敛
                    BASIS_RR_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\BASIS_RR") #配置-操作规范-回流比
                    BASIS_RR_BASIS = self.get_block_type(fr"\Data\Blocks\{block['name']}\Input\BASIS_RR", 13) #配置-操作规范-回流比
                    BASIS_L1_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\BASIS_L1") #配置-操作规范-回流速率
                    BASIS_L1_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\BASIS_L1") #配置-操作规范-回流速率
                    BASIS_L1_BASIS = self.get_block_type(fr"\Data\Blocks\{block['name']}\Input\BASIS_L1", 13) #配置-操作规范-回流速率
                    BASIS_D_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\BASIS_D") #配置-操作规范-馏出物流率
                    BASIS_D_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\BASIS_D") #配置-操作规范-馏出物流率
                    BASIS_D_BASIS = self.get_block_type(fr"\Data\Blocks\{block['name']}\Input\BASIS_D", 13) #配置-操作规范-馏出物流率
                    BASIS_B_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\BASIS_B") #配置-操作规范-塔底物流率
                    BASIS_B_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\BASIS_B") #配置-操作规范-塔底物流率
                    BASIS_B_BASIS = self.get_block_type(fr"\Data\Blocks\{block['name']}\Input\BASIS_B", 13) #配置-操作规范-塔底物流率
                    BASIS_VN_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\BASIS_VN") #配置-操作规范-再沸蒸汽流速
                    BASIS_VN_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\BASIS_VN") #配置-操作规范-再沸蒸汽流速
                    BASIS_VN_BASIS = self.get_block_type(fr"\Data\Blocks\{block['name']}\Input\BASIS_VN", 13) #配置-操作规范-再沸蒸汽流速
                    BASIS_BR_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\BASIS_BR") #配置-操作规范-再沸比
                    BASIS_BR_BASIS = self.get_block_type(fr"\Data\Blocks\{block['name']}\Input\BASIS_L1", 13) #配置-操作规范-再沸比
                    Q1_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\Q1") #配置-操作规范-冷凝器负荷
                    Q1_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\Q1") #配置-操作规范-冷凝器负荷
                    QN_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\QN") #配置-操作规范-再沸器负荷
                    QN_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\QN") #配置-操作规范-再沸器负荷
                    DF_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\D:F") #配置-操作规范-馏出物进料比
                    DF_BASIS = self.get_block_type(fr"\Data\Blocks\{block['name']}\Input\D:F", 13) #配置-操作规范-馏出物进料比
                    BF_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\B:F") #配置-操作规范-馏出物进料比
                    BF_BASIS = self.get_block_type(fr"\Data\Blocks\{block['name']}\Input\B:F", 13) #配置-操作规范-馏出物进料比
                    # RW = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\RW") #配置-自由水回流比  暂不需要
                    blocks_RadFrac_data[block['name']]['CONFIG_DATA'] = {
                        "CALC_MODE": CALC_MODE
                    }
                    # 配置-设置选项
                    if NSTAGE is not None and NSTAGE != "":
                        blocks_RadFrac_data[block['name']]["CONFIG_DATA"]["NSTAGE"] = NSTAGE
                    if CONDENSER is not None and CONDENSER != "":
                        blocks_RadFrac_data[block['name']]["CONFIG_DATA"]["CONDENSER"] = CONDENSER
                    if REBOILER is not None and REBOILER != "":
                        blocks_RadFrac_data[block['name']]["CONFIG_DATA"]["REBOILER"] = REBOILER
                    if CONV_METH is not None and CONV_METH != "":
                        blocks_RadFrac_data[block['name']]["CONFIG_DATA"]["CONV_METH"] = CONV_METH
                    if NO_PHASE is not None and NO_PHASE != "":
                        blocks_RadFrac_data[block['name']]["CONFIG_DATA"]["NO_PHASE"] = NO_PHASE
                    if BLKOPFREWAT is not None and BLKOPFREWAT != "":
                        blocks_RadFrac_data[block['name']]["CONFIG_DATA"]["BLKOPFREWAT"] = BLKOPFREWAT
                    # 配置-操作规范
                    blocks_RadFrac_data[block['name']]['CONFIG_DATA']["OP_SPEC"] = []
                    if BASIS_RR_VALUE is not None and BASIS_RR_VALUE != "":
                        blocks_RadFrac_data[block['name']]['CONFIG_DATA']["OP_SPEC"].append({
                            "BASIS_RR_VALUE": BASIS_RR_VALUE,
                            "BASIS_RR_BASIS": BASIS_RR_BASIS
                        })
                    if BASIS_L1_VALUE is not None and BASIS_L1_VALUE != "":
                        blocks_RadFrac_data[block['name']]['CONFIG_DATA']["OP_SPEC"].append({
                            "BASIS_L1_VALUE": BASIS_L1_VALUE,
                            "BASIS_L1_UNITS": BASIS_L1_UNITS,
                            "BASIS_L1_BASIS": BASIS_L1_BASIS
                        })
                    if BASIS_D_VALUE is not None and BASIS_D_VALUE != "":
                        blocks_RadFrac_data[block['name']]['CONFIG_DATA']["OP_SPEC"].append({
                            "BASIS_D_VALUE": BASIS_D_VALUE,
                            "BASIS_D_UNITS": BASIS_D_UNITS,
                            "BASIS_D_BASIS": BASIS_D_BASIS
                        })
                    if BASIS_B_VALUE is not None and BASIS_B_VALUE != "":
                        blocks_RadFrac_data[block['name']]['CONFIG_DATA']["OP_SPEC"].append({
                            "BASIS_B_VALUE": BASIS_B_VALUE,
                            "BASIS_B_UNITS": BASIS_B_UNITS,
                            "BASIS_B_BASIS": BASIS_B_BASIS
                        })
                    if BASIS_VN_VALUE is not None and BASIS_VN_VALUE != "":
                        blocks_RadFrac_data[block['name']]['CONFIG_DATA']["OP_SPEC"].append({
                            "BASIS_VN_VALUE": BASIS_VN_VALUE,
                            "BASIS_VN_UNITS": BASIS_VN_UNITS,
                            "BASIS_VN_BASIS": BASIS_VN_BASIS
                        })
                    if BASIS_BR_VALUE is not None and BASIS_BR_VALUE != "":
                        blocks_RadFrac_data[block['name']]['CONFIG_DATA']["OP_SPEC"].append({
                            "BASIS_BR_VALUE": BASIS_BR_VALUE,
                            "BASIS_BR_BASIS": BASIS_BR_BASIS
                        })
                    if Q1_VALUE is not None and Q1_VALUE != "":
                        blocks_RadFrac_data[block['name']]['CONFIG_DATA']["OP_SPEC"].append({
                            "Q1_VALUE": Q1_VALUE,
                            "Q1_UNITS": Q1_UNITS
                        })
                    if QN_VALUE is not None and QN_VALUE != "":
                        blocks_RadFrac_data[block['name']]['CONFIG_DATA']["OP_SPEC"].append({
                            "QN_VALUE": QN_VALUE,
                            "QN_UNITS": QN_UNITS
                        })
                    if DF_VALUE is not None and DF_VALUE != "":
                        blocks_RadFrac_data[block['name']]['CONFIG_DATA']["OP_SPEC"].append({
                            "DF_VALUE": DF_VALUE,
                            "DF_BASIS": DF_BASIS
                        })
                    if BF_VALUE is not None and BF_VALUE != "":
                        blocks_RadFrac_data[block['name']]['CONFIG_DATA']["OP_SPEC"].append({
                            "BF_VALUE": BF_VALUE,
                            "BF_BASIS": BF_BASIS
                        })
                    # if RW is not None and RW != "" and RW != 0:
                    #     blocks_RadFrac_data[block['name']]["CONFIG_DATA"]["RW"] = RW
                    #流股抽取
                    FEED_STAGE_NODES = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Input\FEED_STAGE") #流股-进料流股
                    FEED_STAGE_DATA = []
                    for FEED_STAGE in FEED_STAGE_NODES:
                        FEED_STAGE_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\FEED_STAGE\{FEED_STAGE}")
                        FEED_CONVEN = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\FEED_CONVEN\{FEED_STAGE}")  #流股-进料流股-常规
                        FEED_STAGE_DATA.append({
                            "FEED_STAGE": FEED_STAGE,
                            "FEED_STAGE_VALUE": FEED_STAGE_VALUE,
                            "FEED_CONVEN": FEED_CONVEN
                        })
                    blocks_RadFrac_data[block['name']]['FEED_STAGE_DATA'] = FEED_STAGE_DATA
                    PROD_STAGE_NODES = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Input\PROD_STAGE") #流股-产品流股
                    PROD_STAGE_DATA = []
                    for PROD_STAGE in PROD_STAGE_NODES:
                        PROD_STAGE_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PROD_STAGE\{PROD_STAGE}") #流股-产品流股-塔板
                        PROD_PHASE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PROD_PHASE\{PROD_STAGE}")  #流股-产品流股-相态
                        PROD_STAGE_DATA.append({
                            "PROD_STAGE": PROD_STAGE,
                            "PROD_STAGE_VALUE": PROD_STAGE_VALUE,
                            "PROD_PHASE": PROD_PHASE
                        })
                    blocks_RadFrac_data[block['name']]['PROD_STAGE_DATA'] = PROD_STAGE_DATA
                    #压力抽取
                    VIEW_PRES = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\VIEW_PRES")  # 压力-查看
                    blocks_RadFrac_data[block['name']]['PRES_DATA'] = {}
                    blocks_RadFrac_data[block['name']]['PRES_DATA']["VIEW_PRES"] = VIEW_PRES
                    if VIEW_PRES == "TOP/BOTTOM": #压力-查看-塔顶塔底
                        VIEW_PRES_DATA = []
                        PRES1_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PRES1")  # 压力-查看-塔板1压力
                        PRES1_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PRES1")  # 压力-查看-塔板1压力
                        PRES2_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\PRES2")  # 压力-查看-塔板2压力
                        PRES2_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\PRES2")  # 压力-查看-塔板2压力
                        OPT_PRES_TOP = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\OPT_PRES_TOP")  # 压力-查看-塔板2压力-选项
                        DP_COND_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DP_COND")  # 压力-查看-塔板2压力-冷凝器压降
                        DP_COND_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DP_COND")  # 压力-查看-塔板2压力-冷凝器压降
                        OPT_PRES = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\OPT_PRES")  # 压力-查看-塔其余部分压降-选项
                        DP_STAGE_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DP_STAGE")  # 压力-查看-塔其余部分压降-塔板压降
                        DP_STAGE_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DP_STAGE")  # 压力-查看-塔其余部分压降-塔板压降
                        DP_COL_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\DP_COL")  # 压力-查看-塔其余部分压降-塔压降
                        DP_COL_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\DP_COL")  # 压力-查看-塔其余部分压降-塔压降
                        VIEW_PRES_DATA.append({
                            "PRES1_VALUE": PRES1_VALUE,
                            "PRES1_UNITS": PRES1_UNITS,
                            "OPT_PRES_TOP": OPT_PRES_TOP,
                            "PRES2_VALUE": PRES2_VALUE,
                            "PRES2_UNITS": PRES2_UNITS,
                            "DP_COND_VALUE": DP_COND_VALUE,
                            "DP_COND_UNITS": DP_COND_UNITS,
                            "OPT_PRES": OPT_PRES,
                            "DP_STAGE_VALUE": DP_STAGE_VALUE,
                            "DP_STAGE_UNITS": DP_STAGE_UNITS,
                            "DP_COL_VALUE": DP_COL_VALUE,
                            "DP_COL_UNITS": DP_COL_UNITS
                        })
                        blocks_RadFrac_data[block['name']]['PRES_DATA']["STAGE_PRES"] = VIEW_PRES_DATA
                    if VIEW_PRES == "PROFILE": #压力-查看-压力分布
                        STAGE_PRES_NODES = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Input\STAGE_PRES")  # 压力-查看-压力分布
                        STAGE_PRES_DATA = []
                        for PRES_STAGE in STAGE_PRES_NODES:
                            STAGE_PRES_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\STAGE_PRES\{PRES_STAGE}")
                            STAGE_PRES_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\STAGE_PRES\{PRES_STAGE}")
                            STAGE_PRES_DATA.append({
                                "PRES_STAGE": PRES_STAGE,
                                "PRES_VALUE": STAGE_PRES_VALUE,
                                "PRES_UNITS": STAGE_PRES_UNITS
                            })
                        blocks_RadFrac_data[block['name']]['PRES_DATA']["STAGE_PRES"] = STAGE_PRES_DATA
                    #if view_pres == "PDROP":  # 压力-查看-塔段压降  暂未实现

                    # 冷凝器抽取
                    if CONDENSER != "NONE":
                        CONDENSER_DATA = {}
                        OPT_COND_SPC = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\OPT_COND_SPC")  # 冷凝器-冷凝器规范
                        T1_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\T1")  # 冷凝器-冷凝器规范-温度
                        T1_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\T1")  # 冷凝器-冷凝器规范-温度
                        BASIS_RDV_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\BASIS_RDV")  # 冷凝器-冷凝器规范-馏出物汽相分率
                        BASIS_RDV_BASIS = self.get_block_type(fr"\Data\Blocks\{block['name']}\Input\BASIS_RDV", 13)  # 冷凝器-冷凝器规范-馏出物汽相分率
                        SC_TEMP_VALUE = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\SC_TEMP")  # 冷凝器-冷凝器规范-过冷规范-过冷温度
                        SC_TEMP_UNITS = self.safe_get_node_units(fr"\Data\Blocks\{block['name']}\Input\SC_TEMP")  # 冷凝器-冷凝器规范-过冷规范-过冷温度
                        SC_OPTION = self.safe_get_node_value(fr"\Data\Blocks\{block['name']}\Input\SC_OPTION")  # 冷凝器-冷凝器规范
                        self.add_if_not_empty(CONDENSER_DATA, "OPT_COND_SPC", OPT_COND_SPC)
                        self.add_if_not_empty(CONDENSER_DATA, "T1_VALUE", T1_VALUE,"T1_UNITS", T1_UNITS)
                        self.add_if_not_empty(CONDENSER_DATA, "BASIS_RDV_VALUE", BASIS_RDV_VALUE, None, None, "BASIS_RDV_BASIS", BASIS_RDV_BASIS)
                        self.add_if_not_empty(CONDENSER_DATA, "SC_TEMP_VALUE", SC_TEMP_VALUE, "SC_TEMP_UNITS", SC_TEMP_UNITS)
                        self.add_if_not_empty(CONDENSER_DATA, "SC_OPTION", SC_OPTION)
                        blocks_RadFrac_data[block['name']]['CONDENSER_DATA'] = CONDENSER_DATA

                    # 规定-设计规范抽取
                    blocks_RadFrac_data[block['name']]['DESIGN_SPEC_DATA'] = {}
                    design_spec_node = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Subobjects\Design Specs")
                    base_node = fr"\Data\Blocks\{block['name']}\Subobjects\Design Specs"
                    design_spec_data = []
                    for design_spec_id in design_spec_node:
                        SPEC_VALUE = self.safe_get_node_value(fr"{base_node}\{design_spec_id}\Input\VALUE\{design_spec_id}")
                        SPEC_TYPE_VALUE = self.safe_get_node_value(fr"{base_node}\{design_spec_id}\Input\SPEC_TYPE\{design_spec_id}")
                        OPT_SPC_STR_VALUE = self.safe_get_node_value(fr"{base_node}\{design_spec_id}\Input\OPT_SPC_STR\{design_spec_id}")
                        comp_data = []
                        COMPS_NODES = self.get_child_nodes(fr"{base_node}\{design_spec_id}\Input\SPEC_COMPS\{design_spec_id}")
                        for comp_id in COMPS_NODES:
                            comp_value = self.safe_get_node_value(fr"{base_node}\{design_spec_id}\Input\SPEC_COMPS\{design_spec_id}\{comp_id}")
                            comp_data.append(comp_value)
                        spec_streams_data = []
                        SPEC_STREAMS_NODES = self.get_child_nodes(fr"{base_node}\{design_spec_id}\Input\SPEC_STREAMS\{design_spec_id}")
                        for spec_stream_id in SPEC_STREAMS_NODES:
                            spec_stream_value = self.safe_get_node_value(fr"{base_node}\{design_spec_id}\Input\SPEC_STREAMS\{design_spec_id}\{spec_stream_id}")
                            spec_streams_data.append(spec_stream_value)
                        design_spec_data.append({
                            "SPEC_ID": design_spec_id,
                            "SPEC_VALUE": SPEC_VALUE,
                            "SPEC_TYPE_VALUE": SPEC_TYPE_VALUE,
                            "OPT_SPC_STR_VALUE": OPT_SPC_STR_VALUE,
                            "COMP_DATA": comp_data,
                            "SPEC_STREAMS": spec_streams_data
                        })
                        blocks_RadFrac_data[block['name']]['DESIGN_SPEC_DATA'] = design_spec_data
                    # 规定-变化抽取
                    blocks_RadFrac_data[block['name']]['VARY_DATA'] = {}
                    vary_node = self.get_child_nodes(fr"\Data\Blocks\{block['name']}\Subobjects\Vary")
                    base_node = fr"\Data\Blocks\{block['name']}\Subobjects\Vary"
                    vary_data = []
                    for vary_id in vary_node:
                        VAR_VALUE = self.safe_get_node_value(fr"{base_node}\{vary_id}\Input\VALUE\{vary_id}")
                        VARTYPE_VALUE = self.safe_get_node_value(fr"{base_node}\{vary_id}\Input\VARTYPE\{vary_id}")
                        LB_VALUE = self.safe_get_node_value(fr"{base_node}\{vary_id}\Input\LB\{vary_id}")
                        UB_VALUE = self.safe_get_node_value(fr"{base_node}\{vary_id}\Input\UB\{vary_id}")
                        STEP_VALUE = self.safe_get_node_value(fr"{base_node}\{vary_id}\Input\STEP\{vary_id}")
                        comp_data = []
                        COMPS_NODES = self.get_child_nodes(fr"{base_node}\{vary_id}\Input\VARY_COMPS\{vary_id}")
                        for comp_id in COMPS_NODES:
                            comp_value = self.safe_get_node_value(
                                fr"{base_node}\{vary_id}\Input\Vary_COMPS\{vary_id}\{comp_id}")
                            comp_data.append(comp_value)
                        vary_data.append({
                            "VARY_ID": vary_id,
                            "VARY_VALUE": VAR_VALUE,
                            "VARTYPE_VALUE": VARTYPE_VALUE,
                            "LB_VALUE": LB_VALUE,
                            "UB_VALUE": UB_VALUE,
                            "STEP_VALUE": STEP_VALUE,
                            "COMP_DATA": comp_data
                        })
                        blocks_RadFrac_data[block['name']]['VARY_DATA'] = vary_data
                except Exception as e:
                    print(f"提取blocks模块{block['type']}_{block['name']}数据时出错: {e}")
                    continue
            print(f"提取blocks模块RadFrac所有数据完成")
            self.data["blocks_RadFrac_data"] = blocks_RadFrac_data
        except Exception as e:
            print(f"提取blocks模块{blocks_RadFrac['type']}_{blocks_RadFrac['name']}数据时出错: {e}")
    def extract_all_data(self):
        """提取所有数据"""
        print("开始提取 Aspen Plus 数据...")
        self.extract_setup()
        self.extract_components()
        self.extract_property_methods()
        # self.extract_henry_components()  # 新增：提取Henry组分
        self.extract_blocks()
        self.extract_streams()
        self.extract_block_connections()
        self.extract_streams_data()
        self.extract_reactions_data()
        self.extract_convergence_data()
        self.extract_design_specs_data()
        self.extract_block_Mixer_data()
        self.extract_block_Valve_data()
        self.extract_block_Compr_data()
        self.extract_block_Heater_data()
        self.extract_block_Pump_data()
        self.extract_block_RStoic_data()
        self.extract_block_RPlug_data()
        self.extract_block_Flash2_data()
        self.extract_block_Decanter_data()
        self.extract_block_Sep_data()
        self.extract_block_Sep2_data()
        self.extract_block_DSTWU_data()
        self.extract_block_RadFrac_data()
        print("所有数据提取完成")

    def save_to_json(self, output_path: str):
        """将提取的数据保存为 JSON 文件"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            print(f"数据已保存到: {output_path}")
            return True
        except Exception as e:
            print(f"保存 JSON 文件时出错: {e}")
            return False


# 使用示例
if __name__ == "__main__":
  #  converter = AspenToJSONConverter(r"D:\aspen\orgfile\Example11.2.2.6-Final.bkp")
    converter = AspenToJSONConverter(r"D:\aspen\orgfile\Example7.1-DSTWU.bkp")

    if converter.connect_to_aspen():
        try:
            # 提取所有数据
            converter.extract_all_data()

            # 保存为 JSON 文件
         #   output_json_path = r"./Example11.2.2.6-Final.json"
            output_json_path = r"./Example7.1-DSTWU.json"
            converter.save_to_json(output_json_path)

        except Exception as e:
            print(f"处理过程中出错: {e}")
        finally:
            # 断开连接
            converter.disconnect()
    else:
        print("无法连接到 Aspen Plus 文件")