import gym
import numpy as np
from collections import deque
from collections import defaultdict
import pandas as pd
import random

from RL_utils import check_node_memory, vectorize_state
from gym import error, spaces, utils
from bin.main import load_configuration_file, parse_configuration_dict
from simulator.environments.DtnSimEnvironment import DtnSimEnviornment


class CdtnEnvDiscrete(gym.Env):
    """Class representing the lunar scenario environment with all the required functions for the integration with
    openAI gym"""

    def __init__(self):
        """Constructor for lunar scenario environment"""
        # Configuration file path
        config_file = './RL/inputs/lunar_scenario_ASCEND2020.yaml'
        # Load configuration file
        config = load_configuration_file(config_file)
        # Ensure the configuration dictionary is ok
        self.config = parse_configuration_dict(config)
        # Create a simulation environment. From now on, ``config`` will be
        # a global variable available to everyone
        self.env = DtnSimEnviornment(self.config)
        # Initialize environment, create nodes/connections, start generators
        self.env.initialize()
        # Simulation time
        self.simulation_time = 30 * 60
        # RL time step (or action time step) in seconds
        self.time_step = 30  # 60
        # List of nodes connected to RL node (Mission45)
        self.neighbor_nodes = ['Mission26', 'Mission27', 'Mission28', 'Mission29', 'Mission30', 'Mission35',
                               'Mission37', 'Mission38', 'Mission39', 'Mission40', 'Mission44']
        # Radios used by the neighbor nodes for the connection with the RL node (Mission45)
        self.neighbor_nodes_radios = {'Mission26': 'prox_radio',
                                      'Mission27': 'prox_radio',
                                      'Mission28': 'prox_radio',
                                      'Mission29': 'prox_radio',
                                      'Mission30': 'prox_radio',
                                      'Mission35': 'wifi_radio',
                                      'Mission37': 'prox_radio',
                                      'Mission38': 'prox_radio',
                                      'Mission39': 'wifi_radio',
                                      'Mission40': 'wifi_radio',
                                      'Mission44': 'wifi_radio'}
        # Data rate initial values and limits for all the different radio types
        self.radio_data_rate_initial_values = {'in_radio': 1e9,
                                               'out_radio': 1e9}

        self.radio_data_rate_limits = {'in_radio': ((1 / 512) * 1e9, 1e9),
                                       'out_radio': ((1 / 512) * 1e9, 1e9)}

        # Propagation time to change radio data rate
        self.Tprop = 1
        # List of cxl nodes
        self.cxl_node = ['Mission36']
        # List of DSNs connected to RL node (Mission45)
        self.dsn_nodes = ['Mission0', 'Mission34']
        # List of data flow types
        self.data_flows = ['Biomedical', 'Caution and Warning', 'Command and Teleoperation', 'File',
                           'Health and Status', 'Nav Type 1 Products', 'Nav Type 2 Message', 'Network',
                           'PAO HD Video', 'Sci HD Video', 'Science', 'SD Video', 'Voice']

        # Maximum capacity of the incoming and outgoing queues in bits
        self.max_capacity = 80e9  # 800e9

        # Define action and state spaces:
        # The action space in our problem formulation includes 7 different types of actions that the intelligent
        # agent--i.e., the lunar gateway-- can take depending on the current state of the system:
        # 1. Dropping packets. This action is intended to be performed when the gateway node gets very congested and
        #    there is no other way to decongest the network but to start dropping incoming packets.
        # 2. Increasing (doubling) the data rate ($Rb_{in}$) of all links with the neighbor nodes transmitting bundles
        #    to the gateway.
        # 3. Decreasing (by half) the data rate ($Rb_{in}$) of all links with the neighbor nodes transmitting bundles
        #    to the gateway.
        # 4. Increasing (doubling) the data rate ($Rb_{out}$) of the downlinks with the DSN and crosslink.
        # 5. Decreasing (by half) the data rate ($Rb_{out}$) of the downlinks with the DSN and crosslink.
        # 6. Routing bundles through crosslinks instead of sending them straight to the DSN.
        # 7. Do nothing (i.e., not changing any parameter of the network).
        self.action_space = spaces.discrete.Discrete(1 + 2 + 2 + 1 + 1)

        # The state space is defined by network parameters that are available to the lunar gateway at all times. It
        # consists of the node’s memory percentage of utilization, the data rate of all links transmitting bundles to
        # the gateway (assumed the same for all incoming links), and the data rate of the downlinks with the DSNs and
        # the crosslink with the secondary orbital relay (also assumed the same for all outgoing links).
        # The memory utilization percentage is discretized to 3 different values:
        # 1. LOW  (<50%)
        # 2. OK   (>50% and <80%)
        # 3. HIGH (>80%)
        # Similarly, rb_in and rb_out can take 10 possible values between 1 Mbps and 1 Gbps.
        # Therefore, the total number of states in the system under consideration is 3x10x10=300.

        self.possible_values_memory = [0.0, 0.5, 1.0]
        self.multiplicative_factor = 2

        self.possible_values_data_rate_in = []
        data_rate = self.radio_data_rate_limits['in_radio'][0]
        while data_rate <= self.radio_data_rate_limits['in_radio'][1]:
            self.possible_values_data_rate_in.append(data_rate)
            data_rate *= self.multiplicative_factor

        self.possible_values_data_rate_out = []
        data_rate = self.radio_data_rate_limits['out_radio'][0]
        while data_rate <= self.radio_data_rate_limits['out_radio'][1]:
            self.possible_values_data_rate_out.append(data_rate)
            data_rate *= self.multiplicative_factor

        self.observation_space = spaces.discrete.Discrete(len(self.possible_values_memory)
                                                          * len(self.possible_values_data_rate_in)
                                                          * len(self.possible_values_data_rate_out))

        # window that keeps track of the number of bits stored in memory at every time step
        self.bits_mem_window = deque(maxlen=2)
        self.bits_mem_window.append(0)

        # window that keeps track of the number of bits that go through the gateway and arrive at the DSN
        self.bits_arrived_destination_through_45_window = deque(maxlen=2)
        self.bits_arrived_destination_through_45_window.append(0)

    def step(self, action):
        # perform action
        self.perform_action(action)
        # Propagate step
        current_time = self.env.now
        self.env.run(until=(current_time + self.time_step))
        # Observe reward
        reward, benefit, benefit_mod, cost = self.observe_reward()
        # Observe new state
        next_state = self.discretize_state(vectorize_state(self.observe_state()))
        # Check if end of the simulation has been reached
        is_done = (self.env.now >= self.simulation_time)

        return next_state, reward, is_done, {'reward': reward, 'benefit': benefit,
                                             'benefit_mod': benefit_mod, 'cost': cost}

    def reset(self):
        print("ASCEND2020 environment")
        self.bits_mem_window.clear()
        self.bits_mem_window.append(0)
        self.bits_arrived_destination_through_45_window.clear()
        self.bits_arrived_destination_through_45_window.append(0)
        self.env.reset()
        del self.env  # added line
        self.env = DtnSimEnviornment(self.config)  # added line
        self.env.initialize()
        # self.set_datarate_initial_values()
        self.set_datarate_initial_values_random()

        return self.discretize_state(vectorize_state(self.observe_state()))

    def render(self, mode='human', close=False):
        return 0

    def set_datarate_initial_values(self):
        for node_id in self.neighbor_nodes:
            node_to_update = self.env.nodes[node_id]
            radio_type = self.neighbor_nodes_radios[node_id]
            radio_to_update = node_to_update.radios[radio_type]
            radio_to_update.datarate = self.radio_data_rate_initial_values['in_radio']
            neighbour_manager_to_update = node_to_update.queues['Mission45']
            neighbour_manager_to_update.current_dr = self.radio_data_rate_initial_values['in_radio']

        node_to_update = self.env.nodes['Mission45']
        radio_to_update_x = node_to_update.radios['x_dte_radio']
        radio_to_update_x.datarate = self.radio_data_rate_initial_values['out_radio']
        radio_to_update_ka = node_to_update.radios['ka_dte_radio']
        radio_to_update_ka.datarate = self.radio_data_rate_initial_values['out_radio']
        neighbour_manager_to_update = node_to_update.queues['Mission0']
        neighbour_manager_to_update.current_dr = self.radio_data_rate_initial_values['out_radio'] + \
                                                 self.radio_data_rate_initial_values['out_radio']
        neighbour_manager_to_update = node_to_update.queues['Mission34']
        neighbour_manager_to_update.current_dr = self.radio_data_rate_initial_values['out_radio'] + \
                                                 self.radio_data_rate_initial_values['out_radio']

        node_to_update = self.env.nodes['Mission45']
        radio_to_update_cxl = node_to_update.radios['cxl_radio']
        radio_to_update_cxl.datarate = self.radio_data_rate_initial_values['out_radio']
        neighbour_manager_to_update = node_to_update.queues['Mission36']
        neighbour_manager_to_update.current_dr = self.radio_data_rate_initial_values['out_radio']

    def set_datarate_initial_values_random(self):
        rb_in_initial = random.choice(self.possible_values_data_rate_in)
        rb_out_initial = random.choice(self.possible_values_data_rate_out)
        for node_id in self.neighbor_nodes:
            node_to_update = self.env.nodes[node_id]
            radio_type = self.neighbor_nodes_radios[node_id]
            radio_to_update = node_to_update.radios[radio_type]
            radio_to_update.datarate = rb_in_initial
            neighbour_manager_to_update = node_to_update.queues['Mission45']
            neighbour_manager_to_update.current_dr = rb_in_initial

        node_to_update = self.env.nodes['Mission45']
        radio_to_update_x = node_to_update.radios['x_dte_radio']
        radio_to_update_x.datarate = rb_out_initial
        radio_to_update_ka = node_to_update.radios['ka_dte_radio']
        radio_to_update_ka.datarate = rb_out_initial
        neighbour_manager_to_update = node_to_update.queues['Mission0']
        neighbour_manager_to_update.current_dr = rb_out_initial + rb_out_initial
        neighbour_manager_to_update = node_to_update.queues['Mission34']
        neighbour_manager_to_update.current_dr = rb_out_initial + rb_out_initial

        node_to_update = self.env.nodes['Mission45']
        radio_to_update_cxl = node_to_update.radios['cxl_radio']
        radio_to_update_cxl.datarate = rb_out_initial
        neighbour_manager_to_update = node_to_update.queues['Mission36']
        neighbour_manager_to_update.current_dr = rb_out_initial

    def perform_action(self, action):
        self.env.nodes['Mission45'].drop_action.clear()  # The drop actions from previous steps are cancelled
        self.env.nodes['Mission45'].stop_using_cross_link()  # Stop re-routing bundles to cross-link

        if action == 0:
            # Action associated with dropping packets from all users and data types
            print('Starting to drop bundles...')
            node_ids = self.neighbor_nodes
            flow_ids = self.data_flows
            node_45 = self.env.nodes['Mission45']
            for node_id in node_ids:
                for flow_id in flow_ids:
                    # print('Starting to drop bundles from', node_id, 'and data type', flow_id, sep=" ")
                    node_45.drop_action.append((node_id, flow_id))

        elif action == 1:
            print('Increasing data rates of incoming links (neighbours)...')
            node_ids = self.neighbor_nodes

            for node_id in node_ids:
                # print('Increasing data rate of neighbor', node_id, sep=" ")
                node_to_update = self.env.nodes[node_id]
                radio_type = self.neighbor_nodes_radios[node_id]
                radio_to_update = node_to_update.radios[radio_type]
                current_data_rate = radio_to_update.datarate
                new_data_rate = np.minimum(current_data_rate * self.multiplicative_factor,
                                           self.radio_data_rate_limits['in_radio'][1])
                radio_to_update.set_new_datarate(self.Tprop, new_data_rate)
                neighbour_manager_to_update = node_to_update.queues['Mission45']
                neighbour_manager_to_update.set_new_datarate(self.Tprop, new_data_rate)

        elif action == 2:
            print('Decreasing data rates of incoming links (neighbours)...')
            node_ids = self.neighbor_nodes

            for node_id in node_ids:
                # print('Decreasing data rate of neighbor', node_id, sep=" ")
                node_to_update = self.env.nodes[node_id]
                radio_type = self.neighbor_nodes_radios[node_id]
                radio_to_update = node_to_update.radios[radio_type]
                current_data_rate = radio_to_update.datarate
                new_data_rate = np.maximum(current_data_rate / self.multiplicative_factor,
                                           self.radio_data_rate_limits['in_radio'][0])
                radio_to_update.set_new_datarate(self.Tprop, new_data_rate)
                neighbour_manager_to_update = node_to_update.queues['Mission45']
                neighbour_manager_to_update.set_new_datarate(self.Tprop, new_data_rate)

        elif action == 3:
            print('Increasing data rate with DSN and crosslink')
            # print('Increasing data rate DSN radio in  RL node', node_id, sep=" ")
            node_to_update = self.env.nodes['Mission45']
            radio_to_update_x = node_to_update.radios['x_dte_radio']
            current_data_rate_x = radio_to_update_x.datarate
            new_data_rate_x = np.minimum(current_data_rate_x * self.multiplicative_factor,
                                         self.radio_data_rate_limits['out_radio'][1])
            radio_to_update_x.set_new_datarate(self.Tprop, new_data_rate_x)
            radio_to_update_ka = node_to_update.radios['ka_dte_radio']
            current_data_rate_ka = radio_to_update_ka.datarate
            new_data_rate_ka = np.minimum(current_data_rate_ka * self.multiplicative_factor,
                                          self.radio_data_rate_limits['out_radio'][1])
            radio_to_update_ka.set_new_datarate(self.Tprop, new_data_rate_ka)

            neighbour_manager_to_update = node_to_update.queues['Mission0']
            neighbour_manager_to_update.set_new_datarate(self.Tprop, new_data_rate_x + new_data_rate_ka)
            neighbour_manager_to_update = node_to_update.queues['Mission34']
            neighbour_manager_to_update.set_new_datarate(self.Tprop, new_data_rate_x + new_data_rate_ka)

            # print('Increasing data rate of crosslink radio in the RL node', node_id, sep=" ")
            node_to_update = self.env.nodes['Mission45']
            radio_to_update_cxl = node_to_update.radios['cxl_radio']
            current_data_rate_cxl = radio_to_update_cxl.datarate
            new_data_rate_cxl = np.minimum(current_data_rate_cxl * self.multiplicative_factor,
                                           self.radio_data_rate_limits['out_radio'][1])
            radio_to_update_cxl.set_new_datarate(self.Tprop, new_data_rate_cxl)
            neighbour_manager_to_update = node_to_update.queues['Mission36']
            neighbour_manager_to_update.set_new_datarate(self.Tprop, new_data_rate_cxl)

        elif action == 4:
            print('Decreasing data rate with DSN and crosslink')
            # print('Decreasing data rate of DSN radio in RL node', node_id, sep=" ")
            node_to_update = self.env.nodes['Mission45']
            radio_to_update_x = node_to_update.radios['x_dte_radio']
            current_data_rate_x = radio_to_update_x.datarate
            new_data_rate_x = np.maximum(current_data_rate_x / self.multiplicative_factor,
                                         self.radio_data_rate_limits['out_radio'][0])
            radio_to_update_x.set_new_datarate(self.Tprop, new_data_rate_x)
            radio_to_update_ka = node_to_update.radios['ka_dte_radio']
            current_data_rate_ka = radio_to_update_ka.datarate
            new_data_rate_ka = np.maximum(current_data_rate_ka / self.multiplicative_factor,
                                          self.radio_data_rate_limits['out_radio'][0])
            radio_to_update_ka.set_new_datarate(self.Tprop, new_data_rate_ka)

            neighbour_manager_to_update = node_to_update.queues['Mission0']
            neighbour_manager_to_update.set_new_datarate(self.Tprop, new_data_rate_x + new_data_rate_ka)
            neighbour_manager_to_update = node_to_update.queues['Mission34']
            neighbour_manager_to_update.set_new_datarate(self.Tprop, new_data_rate_x + new_data_rate_ka)

            # print('Decreasing data rate of crosslink radio in the RL node', node_id, sep=" ")
            node_to_update = self.env.nodes['Mission45']
            radio_to_update_cxl = node_to_update.radios['cxl_radio']
            current_data_rate_cxl = radio_to_update_cxl.datarate
            new_data_rate_cxl = np.maximum(current_data_rate_cxl / self.multiplicative_factor,
                                           self.radio_data_rate_limits['out_radio'][0])
            radio_to_update_cxl.set_new_datarate(self.Tprop, new_data_rate_cxl)
            neighbour_manager_to_update = node_to_update.queues['Mission36']
            neighbour_manager_to_update.set_new_datarate(self.Tprop, new_data_rate_cxl)

        elif action == 5:
            # Action associated with commanding the RL node to send bundles to cross-link instead of sending to DSNs
            print('Starting to send bundles to cross-link')
            node_45 = self.env.nodes['Mission45']
            node_45.using_cross_link()  # Start using the cross-link and change the route of incoming bundles

        elif action == 6:
            print('Not performing any change in the DTN network')

        else:
            raise RuntimeError('Action index out of bounds')

    def observe_reward(self):
        bits_45_dest_dic = defaultdict(int)
        for nid, node in self.env.nodes.items():
            for bundle in node.endpoints[0]:
                if ('Mission45' in bundle.route) and (
                        bundle.route[-1] == 'Mission0' or bundle.route[-1] == 'Mission34'):
                    bits_45_dest_dic[nid] += bundle.data_vol

        bits_45_dest = sum(bits_45_dest_dic.values())

        # Add the cumulative number of bits arrived from all previous steps and add to queue
        self.bits_arrived_destination_through_45_window.append(np.sum(self.bits_arrived_destination_through_45_window))
        # Compute the number of bits arrived in this time step and add to queue
        self.bits_arrived_destination_through_45_window.append(bits_45_dest -
                                                               self.bits_arrived_destination_through_45_window[-1])

        # Benefit: bits that arrive at destination correctly in current time step
        benefit = self.bits_arrived_destination_through_45_window[-1]

        # Compute bits from node 45 to either of the two DSNs
        datarate_45_x_band = self.env.nodes['Mission45'].radios['x_dte_radio'].datarate
        datarate_45_ka = self.env.nodes['Mission45'].radios['ka_dte_radio'].datarate
        datarate_45_dsn = np.sum([datarate_45_x_band, datarate_45_ka])
        cost_45_dsn = datarate_45_dsn * self.time_step  # bits in current time step

        # Compute bits from any node to node 45
        cost_x_45 = 0
        for node_id in self.neighbor_nodes:
            datarate_node_i_45 = self.env.nodes[node_id].radios[self.neighbor_nodes_radios[node_id]].datarate
            cost_node_i_45 = datarate_node_i_45 * self.time_step  # bits in current time step
            cost_x_45 += cost_node_i_45

        # Compute bits from node 45 to node 36 (cross-link)
        datarate_45_node_36 = self.env.nodes['Mission45'].radios['cxl_radio'].datarate
        cost_45_36 = datarate_45_node_36 * self.time_step  # bits in current time step

        # Cost: sum of all the costs of all links controlled by node 45
        cost = cost_45_dsn + cost_x_45 + cost_45_36

        # Compute bits in memory
        state = self.observe_state()
        memory_utilization = state['memory']
        bits_mem = memory_utilization[0] * self.max_capacity
        self.bits_mem_window.append(bits_mem - self.bits_mem_window[-1])
        mem_factor = self.compute_memory_factor(bits_mem)

        # Compute modulation factor
        eta = datarate_45_dsn / (2 * self.radio_data_rate_limits['out_radio'][1])
        mod_factor = (2 ** eta - 1) / eta

        # Compute backpropagation factor
        mem_factor_backpropagation, _ = self.compute_backpropagation_memory_factor()

        # Compute reward signal
        reward_total = (benefit / mod_factor / cost) * mem_factor * mem_factor_backpropagation

        return reward_total, benefit, benefit / mod_factor, cost

    def observe_state(self):
        node_45 = self.env.nodes['Mission45']
        memory_state = check_node_memory(node_45)

        data_rates_in = []
        data_rates_out = []
        for node_id in self.neighbor_nodes:
            neighbor_node = self.env.nodes[node_id]
            radio_node = neighbor_node.radios[self.neighbor_nodes_radios[node_id]]
            data_rates_in.append(radio_node.datarate)

        node_45 = self.env.nodes['Mission45']
        radio_cxl = node_45.radios['cxl_radio']
        radio_x = node_45.radios['x_dte_radio']
        radio_ka = node_45.radios['ka_dte_radio']
        data_rates_out.append(radio_cxl.datarate)
        data_rates_out.append(radio_x.datarate)
        data_rates_out.append(radio_ka.datarate)

        # check all out data rates are the same
        check = len(data_rates_in) > 0 and all(elem == data_rates_in[0] for elem in data_rates_in)
        if not check:
            raise RuntimeError('data rates of neighbour nodes are not all the same')
        # check all in data rates are the same
        check = len(data_rates_out) > 0 and all(elem == data_rates_out[0] for elem in data_rates_out)
        if not check:
            raise RuntimeError('data rates of DSN and crosslink are not the same')

        return {"memory": [memory_state[1]],
                "in_data_rate": [data_rates_in[0]],
                "out_data_rate": [data_rates_out[0]]}

    def observe_bits_in_memory_neighbors(self):
        dict_memory = {}
        for node_id in self.neighbor_nodes:
            incoming_traffic = 0
            outgoing_traffic = 0
            node = self.env.nodes[node_id]
            for bundle in node.in_queue:
                incoming_traffic += bundle[0].data_vol
            for bundle in node.limbo_queue:
                incoming_traffic += bundle[0].data_vol
            for nid, neighbor_manager in node.queues.items():
                # Skipping opportunistic queues
                if neighbor_manager is None:
                    continue
                # Check number of bundles in neighbour queue and create record
                neighbor_queue = neighbor_manager.queue.queue
                for priority in neighbor_queue.priorities:
                    # If this priority level is empty, continue
                    if not any(neighbor_queue.items[priority]): continue
                    for rtn_record in neighbor_queue.items[priority]:
                        outgoing_traffic += rtn_record.bundle.data_vol
            dict_memory[node_id] = incoming_traffic + outgoing_traffic
        return dict_memory

    def compute_backpropagation_memory_factor(self):
        memory_utilization_all_nodes = []
        for node_id in self.neighbor_nodes:
            memory_utilization = check_node_memory(self.env.nodes[node_id])
            memory_utilization_all_nodes.append(memory_utilization[0] + memory_utilization[1])
        for node_id in self.cxl_node:
            memory_utilization = check_node_memory(self.env.nodes[node_id])
            memory_utilization_all_nodes.append(memory_utilization[0] + memory_utilization[1])

        max_utilization = np.max(memory_utilization_all_nodes)
        a = -25
        return 1 / (1 + np.exp(a * (0.8 - max_utilization))), memory_utilization_all_nodes

    def compute_memory_factor_60(self, bits_memory):
        x = bits_memory / self.max_capacity
        a = -25
        return 1 / (1 + np.exp(a * (0.8 - x)))

    def compute_memory_factor(self, bits_memory):
        x = bits_memory / self.max_capacity
        a = -50
        return 1 / (1 + np.exp(a * (0.9 - x)))

    def compute_simulation_results(self):
        # Validate simulation
        ok = self.env.validate_simulation()
        # Create simulation outputs
        res = self.env.finalize_simulation()

        return ok, res

    def compute_packets_received_and_lost(self):
        packets_received_dsn = len(self.env.nodes['Mission0'].endpoints[0]) + \
                               len(self.env.nodes['Mission34'].endpoints[0])
        packets_dropped_mission45 = len(self.env.nodes['Mission45'].dropped)

        return {'packets_received': packets_received_dsn,
                'packets_dropped': packets_dropped_mission45}

    def discretize_state(self, vector_state):
        memory = vector_state[0]
        data_rate_in = vector_state[1]
        data_rate_out = vector_state[2]

        if memory < 0.5:
            memory_modified = 0.0
        elif 0.5 <= memory <= 0.8:
            memory_modified = 0.5
        elif memory > 0.8:
            memory_modified = 1.0
        else:
            raise RuntimeError('Something went wrong. Memory needs to be between 0 and 1')

        memory_index = self.possible_values_memory.index(memory_modified)
        data_rate_in_index = self.possible_values_data_rate_in.index(data_rate_in)
        data_rate_out_index = self.possible_values_data_rate_out.index(data_rate_out)

        n_memory = len(self.possible_values_memory)
        n_data_rate_in = len(self.possible_values_data_rate_in)
        n_data_rate_out = len(self.possible_values_data_rate_out)

        return memory_index * (
                n_data_rate_in * n_data_rate_out) + data_rate_in_index * n_data_rate_out + data_rate_out_index
