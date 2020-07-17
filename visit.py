from copy import deepcopy

from solidity_parser.parser import Node


class ASTVisitor:
    def __init__(self):
        self._result = []
        self._called_functions = None
        self._reset_count()

    def get_result(self):
        return self._result

    def _reset_count(self):
        self._count = {
            'name': '',
            'assignment': 0,  # 函数块内赋值（包括自增自减语句）的个数
            'if': 0,  # 函数块内if块的个数
            'loop': 0,  # 函数块内循环块的个数
            'var_definition': 0,  # 函数块内变量定义的个数
            'emit': 0,  # 函数块内emit语句的个数
            'guarantee': 0,  # 函数块内assert/require等语句的个数
            'function_call': 0,  # 函数块内函数调用语句的个数
            'rhs_msgsender': 0,  # x = msg.sender语句的个数
            'owner_is_msgsender': 0,  # owner = msg.sender语句的个数
            'lhs_balance_assign': 0,  # balance[x] = y语句的个数
            'lhs_balance_owner_assign': 0,  # balance[owner] = x / balance[msg.sender] = x语句的个数
            'is_constructor': None,  # 是否为构造函数
            'visibility': [],  # 可见性
            'modifier_names': [],  # 修饰符名称列表
            'is_called': False
        }

    def visit_ContractDefinition(self, node):
        self._called_functions = set()

    def visited_ContractDefinition(self, node):
        for i in range(len(self._result)):
            self._result[i]['is_called'] = self._result[i]['name'] in self._called_functions

    def visit_FunctionDefinition(self, node):
        self._reset_count()
        self._count['name'] = node['name']
        self._count['is_constructor'] = node['isConstructor']
        self._count['visibility'] = node['visibility']
        self._count['modifier_names'] = [x['name'] for x in node['modifiers']]

    def visited_FunctionDefinition(self, node):
        self._result.append(deepcopy(self._count))

    def visit_IfStatement(self, node):
        self._count['if'] += 1

    def visit_WhileStatement(self, node):
        self._count['loop'] += 1

    def visit_ForStatement(self, node):
        self._count['loop'] += 1

    def visit_DoWhileStatement(self, node):
        self._count['loop'] += 1

    def visit_VariableDefinitionStatement(self, node):
        self._count['var_definition'] += 1

    def visit_EmitStatement(self, node):
        self._count['emit'] += 1

    def _normal_assign_analysis(self, lhs, rhs):
        sender_spec = {
            'type': 'MemberAccess',
            'expression': {
                'type': 'Identifier',
                'name': 'msg'
            },
            'memberName': 'sender'
        }

        # Check the xxx = msg.sender (rightHandSide = msg.sender)
        if rhs == sender_spec:
            self._count['rhs_msgsender'] += 1
            # especially .*?owner.*? = msg.sender
            if lhs['type'] == 'Identifier' and 'owner' in str(
                    lhs['name']).lower():
                self._count['owner_is_msgsender'] += 1

        # Check balance initialization, formulae: balance[x] = y
        if lhs['type'] == 'IndexAccess' \
                and lhs['base']['type'] == 'Identifier' \
                and 'balance' in str(lhs['base']['name']).lower():
            self._count['lhs_balance_assign'] += 1
            # Left hand side is balance[owner|msg.sender]
            cond1 = lhs['index']['type'] == 'Identifier' and 'owner' in str(lhs['index']['name']).lower()
            cond2 = lhs['index'] == sender_spec
            if cond1 or cond2:
                self._count['lhs_balance_owner_assign'] += 1

    def visit_ExpressionStatement(self, node):
        if node['expression'] is None:
            print('Node None', node)
        if node['expression']['type'] == 'FunctionCall':
            # Some other situations, ignore
            if 'name' not in node['expression']['expression']:
                # print('No name')
                return
            # Statements that are for 'guarantee' something
            if node['expression']['expression']['name'] in ['require', 'assert', 'revert']:
                self._count['guarantee'] += 1
                return
            # Normal function call
            self._count['function_call'] += 1
            self._called_functions.add(node['expression']['expression']['name'])
            return

        if 'operator' not in node['expression']:
            return

        if node['expression']['operator'] in ('=', '+=', '-=', '++', '--', '*=', '/=', '<<=', '>>='):
            self._count['assignment'] += 1

        if node['expression']['operator'] == '=':
            self._normal_assign_analysis(node['expression']['left'], node['expression']['right'])

    @staticmethod
    def run(ast: Node):
        visitor = ASTVisitor()

        def run_visitors(root: Node, visitor):
            method = 'visit_' + root.get('type')
            if hasattr(visitor, method):
                stop_visit = getattr(visitor, method)(root)
                if stop_visit:
                    return

            for k, v in root.items():
                if k in root.NONCHILD_KEYS:
                    # skip non child items
                    continue

                # item is array?
                if isinstance(v, list):
                    sub_nodes = v
                elif isinstance(v, Node):
                    sub_nodes = [v]
                else:
                    continue

                for sub_node in sub_nodes:
                    if not isinstance(sub_node, Node):
                        continue
                    run_visitors(sub_node, visitor)

            method = 'visited_' + root.get('type')
            if hasattr(visitor, method):
                getattr(visitor, method)(root)

        run_visitors(ast, visitor)
        return visitor
